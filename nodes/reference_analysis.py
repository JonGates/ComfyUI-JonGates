# SPDX-License-Identifier: MIT
# Copyright (c) 2026 JonGates

import base64
import gc
import io
import json
from pathlib import Path
import threading

_LOCK = threading.RLock()
FIELDS = ('source_identity', 'source_clothing', 'source_items', 'source_scene', 'source_pose',
          'reference_scene', 'reference_clothing', 'reference_pose', 'reference_style')


def validate_analysis(text):
    data = json.loads(text)
    if not isinstance(data, dict) or any(not isinstance(data.get(k), str) or not data[k].strip() for k in FIELDS):
        raise ValueError('双图分析未返回完整的九个描述字段，请重新运行分析。')
    return json.dumps({k: data[k].strip() for k in FIELDS}, ensure_ascii=False)


def _choices():
    import folder_paths
    if 'LLM' not in folder_paths.folder_names_and_paths:
        folder_paths.add_model_folder_path('LLM', str(Path(folder_paths.models_dir)/'LLM'))
        folder_paths.folder_names_and_paths['LLM'][1].add('.gguf')
    names = folder_paths.get_filename_list('LLM')
    models = [n for n in names if n.lower().endswith('.gguf') and 'mmproj' not in n.lower()]
    projectors = [n for n in names if 'mmproj' in n.lower()]
    return models or ['未找到GGUF'], projectors or ['未找到mmproj']


def _image_url(tensor):
    import numpy as np
    from PIL import Image
    if tensor.ndim != 4 or tensor.shape[0] != 1:
        raise ValueError('双图分析每个输入仅支持一张图片。')
    im = Image.fromarray(np.clip(tensor[0].detach().cpu().numpy()*255,0,255).astype(np.uint8)).convert('RGB')
    im.thumbnail((768,768),Image.Resampling.LANCZOS)
    b=io.BytesIO();im.save(b,format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode('ascii')


class JonGatesReferenceAnalysis:
    @classmethod
    def INPUT_TYPES(cls):
        models,projectors=_choices()
        model=next((n for n in models if 'PE-T2I.Q5_K_M' in n),models[0])
        proj=next((n for n in projectors if 'PE-I2I.mmproj-bf16' in n),projectors[0])
        return {'required':{'source':('IMAGE',),'reference':('IMAGE',),
                'model_name':(models,{'default':model}),'mmproj_name':(projectors,{'default':proj}),
                'seed':('INT',{'default':666,'min':0,'max':0xFFFFFFFF,'control_after_generate':True})}}

    RETURN_TYPES=('STRING',)
    RETURN_NAMES=('analysis_json',)
    FUNCTION='analyze'
    CATEGORY='JonGates/Qwen'
    DESCRIPTION='使用本机已有PE GGUF与mmproj做双图结构化观察；分别记录原人物、原服装、原物品和参考场景/服装/姿态/色调。分析结束卸载LLM。需要llama-cpp-python的Qwen35ChatHandler。'

    def analyze(self, source, reference, model_name, mmproj_name, seed=666):
        import folder_paths
        import comfy.model_management as mm
        try:
            from llama_cpp import Llama
            from llama_cpp.llama_chat_format import Qwen35ChatHandler
        except ImportError as e:
            raise RuntimeError('当前Python环境需要支持Qwen35ChatHandler的llama-cpp-python。') from e
        _choices()
        model=folder_paths.get_full_path('LLM',model_name)
        proj=folder_paths.get_full_path('LLM',mmproj_name)
        if not model or not proj:raise ValueError('找不到所选GGUF或mmproj模型。')
        schema={'type':'object','properties':{k:{'type':'string'} for k in FIELDS},'required':list(FIELDS),'additionalProperties':False}
        system='你是严谨的双图摄影内容观察器，只观察真实可见内容，不生成编辑命令。第一张是source原人物，第二张是reference参考。用中文填写JSON各字段，不互换两张图。不要抄写水印、字幕、标志文字、视频播放图标或界面元素。'
        task=('观察两张图，输出JSON。source_identity只描述第一张人物面部和头发；source_clothing只写第一张服装款式颜色纹样；'
              'source_items写第一张真实可见的帽子、发饰、包、首饰、花束及手持物，没有则写无；'
              'source_scene写第一张背景；source_pose写第一张身体朝向和双手动作。'
              'reference_scene只写第二张场景环境和支撑动作的物体，绝不包含人物、衣服、文字或水印；'
              'reference_clothing只写第二张主角的衣服；reference_pose只写第二张主角的身体朝向、头部、肩肘手腕动作，不描述衣服长相；'
              'reference_style只写第二张摄影光线、白平衡、色彩倾向、影调和景深，不写物体或人物外貌。'
              '保持简短，每字段不超过120字。无法看清的内容明确写无法判断，不猜测出画部分。')
        content=[{'type':'text','text':task}]+[{'type':'image_url','image_url':{'url':_image_url(im)}} for im in (source,reference)]
        with _LOCK:
            mm.throw_exception_if_processing_interrupted()
            mm.unload_all_models();mm.soft_empty_cache()
            llm=handler=None
            try:
                handler=Qwen35ChatHandler(mmproj_path=proj,use_gpu=True,add_vision_id=True,enable_thinking=False,verbose=False)
                llm=Llama(model_path=model,chat_handler=handler,n_gpu_layers=-1,n_ctx=16384,n_batch=2048,n_ubatch=512,verbose=False)
                result=llm.create_chat_completion(messages=[{'role':'system','content':system},{'role':'user','content':content}],
                    response_format={'type':'json_object','schema':schema},temperature=0.1,top_p=0.9,top_k=30,
                    seed=int(seed),max_tokens=2200,reasoning_budget=0)
                mm.throw_exception_if_processing_interrupted()
                return (validate_analysis(result['choices'][0]['message']['content']),)
            finally:
                if llm is not None:llm.close()
                elif handler is not None and callable(getattr(handler,'close',None)):handler.close()
                del llm,handler
                gc.collect();mm.soft_empty_cache()


NODE_CLASS_MAPPINGS={'JonGatesReferenceAnalysis':JonGatesReferenceAnalysis}
NODE_DISPLAY_NAME_MAPPINGS={'JonGatesReferenceAnalysis':'双图结构化分析 (JonGates)'}
