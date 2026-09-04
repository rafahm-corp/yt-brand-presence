import os
import json
import configparser
import re
import time
from client_factory import create_genai_client, generate_content_with_retry, get_model_names
from google.genai import types
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def call_gemini(prompt, model_name, fallback_model_name="gemini-3.6-flash", config=None, client=None, config_path=None):
    """Calls Gemini API using unified generate_content_with_retry."""
    if client is None:
        client = create_genai_client(config_path=config_path)
        
    try:
        response = generate_content_with_retry(
            client=client,
            model=model_name,
            contents=prompt,
            config=config,
            fallback_model=fallback_model_name
        )
        if response and response.text:
            return response.text
    except Exception as e:
        print(f"Error calling Gemini in slide generation: {e}", flush=True)

    return None

def generate_image(prompt, output_path, client=None, config_path=None):
    """Calls Gemini Image API to generate presentation slide images."""
    if client is None:
        client = create_genai_client(config_path=config_path)
    
    models_to_try = ["gemini-2.5-flash-image", "gemini-3.1-flash-image", "gemini-3-pro-image"]
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt],
                )
                
                for part in response.parts:
                    if hasattr(part, "as_image") and callable(part.as_image):
                        try:
                            img = part.as_image()
                            if img:
                                img.save(output_path)
                                return True
                        except Exception:
                            pass
                    if hasattr(part, "inline_data") and part.inline_data is not None:
                        from io import BytesIO
                        data = part.inline_data.data
                        if isinstance(data, str):
                            import base64
                            data = base64.b64decode(data)
                        img = Image.open(BytesIO(data))
                        img.save(output_path)
                        return True
            except Exception as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e):
                    time.sleep(3)
                else:
                    break
    print(f"Failed to generate image for {output_path}", flush=True)
    return False

def run_slide_generation(config_path="config.ini"):
    """Full workflow to generate slides content as JSON, images and HTML/PDF presentation deck."""
    conf_file = config_path if os.path.isabs(config_path) else os.path.join(PROJECT_ROOT, config_path)
    config_dir = os.path.dirname(os.path.abspath(conf_file))
    
    config = configparser.ConfigParser(interpolation=None)
    config.read(conf_file)
    
    target_brand = config.get('Target', 'target_brand', fallback='Target Brand')
    category_theme = config.get('Category', 'category_theme', fallback='Category Strategy')
    safe_theme = re.sub(r'\W+', '', category_theme.replace(' ', '_'))
    safe_brand = re.sub(r'\W+', '', target_brand.replace(' ', '_'))
    
    run_id = config.get('General', 'run_id', fallback=f"{safe_brand}_{safe_theme}")
    additional_context = config.get('Analysis', 'additional_context', fallback='')
    output_language = config.get('Analysis', 'output_language', fallback='Portuguese')
    
    models = get_model_names(conf_file)
    pro_model_name = models.get('pro_model_name', 'gemini-flash-latest')
    flash_model_name = models.get('flash_model_name', 'gemini-flash-latest')
    fallback_model_name = models.get('fallback_model_name', 'gemini-3.6-flash')
    
    client = create_genai_client(config_path=conf_file)
    
    run_dir = os.path.join(config_dir, "outputs", run_id)
    report_file = os.path.join(run_dir, f"{target_brand}_final_analysis_report.md")
    if not os.path.exists(report_file):
        report_file = os.path.join(run_dir, f"{safe_brand}_final_analysis_report.md")
    if not os.path.exists(report_file):
        report_file = os.path.join(run_dir, f"{target_brand}_brand_presence_report.md")
    if not os.path.exists(report_file):
        report_file = os.path.join(run_dir, f"{safe_brand}_brand_presence_report.md")
    if not os.path.exists(report_file):
        md_cands = glob.glob(os.path.join(run_dir, "*_final_analysis_report.md")) or glob.glob(os.path.join(run_dir, "*_report.md")) or glob.glob(os.path.join(run_dir, "*.md"))
        if md_cands:
            report_file = md_cands[0]
        
    output_dir = os.path.join(run_dir, "presentation_structured")
    images_dir = os.path.join(output_dir, "images_full")
    os.makedirs(images_dir, exist_ok=True)
    
    if not os.path.exists(report_file):
        print(f"Error: Strategic report file not found at {report_file}", flush=True)
        return None
        
    with open(report_file, 'r', encoding='utf-8') as f:
        report_content = f.read()
        
    # STEP 1: Designer Agent - Generates the Template/Design System
    designer_prompt = f"""
    Você é o Designer Agent. Com base no conteúdo do relatório de inteligência de marca sobre '{target_brand}' na categoria '{category_theme}', 
    gere um Design System completo para uma apresentação executiva (Deck de 16:9).
    
    O output deve conter:
    - Paleta de Cores (Hex codes)
    - Tipografia (Fontes e tamanhos)
    - Descrição do Estilo Visual Profissional
    
    Relatório:
    {report_content[:5000]}
    """
    
    print("\n--- Gerando Template de Design dos Slides ---", flush=True)
    design_template = call_gemini(designer_prompt, flash_model_name, fallback_model_name, client=client, config_path=conf_file)
    if not design_template:
        return None
    print("SUCCESS: Template de Design gerado.", flush=True)
        
    # STEP 2: Slider Buddy - Generates content for EXACTLY 8 slides in JSON
    slider_buddy_prompt_path = os.path.join(PROJECT_ROOT, 'templates', 'prompts', 'slider_buddy.txt')
    with open(slider_buddy_prompt_path, 'r', encoding='utf-8') as f:
        slider_buddy_prompt_base = f.read()
        
    prompt_step2 = f"""
    {slider_buddy_prompt_base}
    
    Instrução Específica: Gere o conteúdo para EXATAMENTE 8 slides executivos sobre a marca '{target_brand}' no tema '{category_theme}'.
    Slide 1 deve ser sempre a Capa (Cover).
    
    Retorne o resultado APENAS como um JSON list de objetos. Não inclua markdown ou explicações fora do JSON.
    Cada objeto deve ter a seguinte estrutura:
    {{
      "slide": 1,
      "headline": "Título do slide",
      "subtitle": "Subtítulo (opcional)",
      "bullets": ["Tópico 1", "Tópico 2", ...],
      "visual_description": "Descrição detalhada do visual e layout para este slide"
    }}
    
    Conteúdo do Relatório:
    {report_content[:6000]}
    """
    
    if additional_context:
        prompt_step2 += f"\n\nInformações/Diretrizes Adicionais do Usuário:\n{additional_context}"
        
    prompt_step2 += f"\n\nIDIOMA DE SAÍDA: Toda a apresentação e textos devem ser gerados no idioma: {output_language}."
    
    print("\n--- Gerando Conteúdo dos Slides (JSON) ---", flush=True)
    json_config = types.GenerateContentConfig(response_mime_type="application/json")
    
    slides_json = call_gemini(prompt_step2, flash_model_name, fallback_model_name, config=json_config, client=client, config_path=conf_file)
    if not slides_json:
        return None
        
    try:
        slides_list = json.loads(slides_json)
        print("SUCCESS: Conteúdo dos slides gerado em JSON.", flush=True)
    except Exception as e:
        print(f"Error parsing JSON from Gemini: {e}", flush=True)
        return None
        
    with open(os.path.join(output_dir, "template.yaml"), 'w', encoding='utf-8') as f:
        f.write(design_template)
    with open(os.path.join(output_dir, "slides_content.json"), 'w', encoding='utf-8') as f:
        f.write(slides_json)
        
    from concurrent.futures import ThreadPoolExecutor, as_completed
    print(f"\n--- Gerando Imagens para {len(slides_list)} slides (Paralelo) ---", flush=True)
    
    def process_slide(item):
        slide_num = item.get('slide')
        headline = item.get('headline')
        bullets = item.get('bullets', [])
        visual = item.get('visual_description')
        
        print(f"Processando Slide {slide_num}...", flush=True)
        bullets_text = "\n".join([f"- {b}" for b in bullets])
        
        prompt_generator = f"""
        Com base no seguinte Design System e no conteúdo deste slide,
        gere um prompt detalhado e em INGLÊS para o gerador de imagens (16:9 Presentation Deck).
        O prompt deve descrever o slide inteiro como uma imagem visualmente impactante, incluindo título, subtítulo e bullets.
        Instrua o gerador a renderizar os textos no idioma: {output_language}.
        
        Design System:
        {design_template}
        
        Conteúdo do Slide:
        Título: {headline}
        Texto: {bullets_text}
        Direção Visual: {visual}
        """
        
        image_prompt = call_gemini(prompt_generator, flash_model_name, fallback_model_name, client=client, config_path=conf_file)
        if not image_prompt:
            image_prompt = f"Professional corporate 16:9 presentation slide about '{headline}'. Clean layout, high contrast text in {output_language}: {headline}\n{bullets_text}"
            
        output_image_path = os.path.join(images_dir, f"slide_{slide_num:02d}.png")
        print(f"Gerando Imagem para Slide {slide_num}...", flush=True)
        success = generate_image(image_prompt, output_image_path, client=client, config_path=conf_file)
        
        if success:
            print(f"SUCCESS: Imagem do Slide {slide_num} criada.", flush=True)
        else:
            print(f"Aviso: Falha ao gerar imagem para Slide {slide_num}.", flush=True)
            
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_slide, item) for item in slides_list]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Erro no processamento do slide: {e}", flush=True)
        
    # STEP 4: Create HTML Viewer
    print("\n--- Criando Visualizador HTML do Deck ---", flush=True)
    output_html = os.path.join(run_dir, f"{target_brand}_deck.html")
    
    img_files = [f for f in os.listdir(images_dir) if f.endswith('.png')]
    img_files.sort(key=lambda x: int(re.search(r'slide_(\d+)', x).group(1)) if re.search(r'slide_(\d+)', x) else 0)
    
    import base64
    html_slides_str = ""
    for img_file in img_files:
        img_path = os.path.join(images_dir, img_file)
        with open(img_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
        html_slides_str += f"""
        <div class="slide">
            <img src="data:image/png;base64,{encoded_string}" alt="Slide">
        </div>
        """
        
    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Deck de Apresentação Executive - {target_brand}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 25px; text-align: center; }}
        .container {{ max-width: 1050px; margin: 0 auto; }}
        .slide {{ margin-bottom: 35px; border: 1px solid #334155; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
        img {{ width: 100%; height: auto; display: block; }}
        h1 {{ color: #60a5fa; margin-bottom: 25px; font-size: 2rem; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Apresentação de Slides Executiva: {target_brand}</h1>
        {html_slides_str}
    </div>
</body>
</html>"""
    
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"SUCCESS: Saved HTML Deck to {output_html}", flush=True)
    
    # STEP 5: Create PDF Presentation
    print("\n--- Criando PDF da Apresentação ---", flush=True)
    output_pdf = os.path.join(run_dir, f"{target_brand}_presentation.pdf")
    
    images = [Image.open(os.path.join(images_dir, f)) for f in img_files if f.endswith('.png')]
    rgb_images = []
    for img in images:
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            rgb_images.append(background)
        else:
            rgb_images.append(img.convert('RGB'))
            
    if rgb_images:
        rgb_images[0].save(output_pdf, save_all=True, append_images=rgb_images[1:])
        print(f"SUCCESS: Saved PDF Presentation to '{output_pdf}'", flush=True)
        return output_pdf
    else:
        print("Aviso: Nenhuma imagem disponível para gerar PDF.", flush=True)
        return None

if __name__ == "__main__":
    run_slide_generation()
