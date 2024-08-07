import requests
import time
import json
import csv
from deep_translator import GoogleTranslator
from llamaapi import LlamaAPI

# Função para buscar dados do candidato
def fetch_candidate_data(candidate_id):
    url = f"https://api.candidato.bne.com.br/api/v1/Curriculum/MinData/{candidate_id}"
    headers = {
        'authority': 'api.candidato.bne.com.br',
        'accept': 'application/json, text/plain, /',
        'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'origin': 'https://www.bne.com.br',
        'referer': 'https://www.bne.com.br/',
        'sec-ch-ua': '"Chromium";v="112", "Google Chrome";v="112", "Not:A-Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Levanta um HTTPError para respostas ruins
        return response.json()
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            print(f"Dados do candidato {candidate_id} não encontrados (404).")
        else:
            print(f"Erro ao buscar dados do candidato {candidate_id}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar dados do candidato {candidate_id}: {e}")
        return None

# Caminho para o arquivo de saída dos candidatos
output_file_path = "candidatos.json"

# Buscar dados para 11 candidatos
candidatos = []
for candidate_id in range(1, 2000):
    candidate_data = fetch_candidate_data(candidate_id)
    if candidate_data:
        candidatos.append(candidate_data)
    # Para evitar sobrecarregar o servidor, adicionar um delay
    time.sleep(0.2)

# Salvar os dados dos candidatos em um arquivo JSON
with open(output_file_path, "w", encoding="utf-8") as file:
    json.dump(candidatos, file, ensure_ascii=False, indent=4)

print(f"Dados dos candidatos foram salvos em {output_file_path}")

# Inicializa o SDK do Llama
llama = LlamaAPI("************************************************** ***********************")

# Inicializa o tradutor
translator = GoogleTranslator(source='auto', target='pt')

# Função para verificar se o candidato atende aos critérios
def verificar_criterios(curriculo):
    idade = curriculo.get('Idade', 0)
    escolaridade = curriculo.get('Des_Escolaridade', '')
    atividades = " ".join(curriculo.get('Des_Atividade', []))
    cursos = " ".join(curriculo.get('Des_Curso', []))
    
    idade_adequada = 25 <= idade <= 40
    escolaridade_adequada = escolaridade.lower() == "superior completo"
    experiencia_adequada = any(keyword in atividades.lower() for keyword in ["administração", "financeiro"])
    
    return idade_adequada, escolaridade_adequada, experiencia_adequada

# Função para criar o prompt e analisar o currículo
def analisar_curriculo(curriculo):
    idade = curriculo.get('Idade', 0)
    escolaridade = curriculo.get('Des_Escolaridade', '')
    atividades = " ".join(curriculo.get('Des_Atividade', []))
    cursos = " ".join(curriculo.get('Des_Curso', []))
    
    prompt = (
        f"Idade: {idade}\n"
        f"Escolaridade: {escolaridade}\n"
        f"Atividades: {atividades}\n"
        f"Cursos: {cursos}\n\n"
        f"O candidato tem entre 25 e 40 anos, possui curso superior completo e experiência ligada a administração ou financeiro?"
    )
    
    api_request_json = {
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "max_token": 500,
        "temperature": 0.1,
        "top_p": 1.0,
        "frequency_penalty": 1.0
    }

    try:
        response = llama.run(api_request_json)
        if response.status_code != 200:
            print(f"Erro na resposta da API Llama: {response.status_code} - {response.text}")
            return "Erro na avaliação"
        content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
        if not content:
            print("Conteúdo da resposta da API Llama está vazio.")
            return "Erro na avaliação"
        traducao = translator.translate(content)
        return traducao
    except Exception as e:
        print(f"Erro ao analisar currículo com Llama: {e}")
        return "Erro na avaliação"

# Analisar currículos e exportar resultados para CSV
resultados = []
with open(output_file_path, "r", encoding="utf-8") as file:
    candidatos = json.load(file)
    for curriculo in candidatos:
        idade_adequada, escolaridade_adequada, experiencia_adequada = verificar_criterios(curriculo)
        status = "Apto" if (idade_adequada and escolaridade_adequada and experiencia_adequada) else "Inapto"
        avaliacao_llama = analisar_curriculo(curriculo)
        resultado = {
            'Nome': curriculo.get('Nme_Pessoa', ''),
            'Idade': curriculo.get('Idade', 0),
            'Escolaridade': curriculo.get('Des_Escolaridade', ''),
            'Atividades': " ".join(curriculo.get('Des_Atividade', [])),
            'Cursos': " ".join(curriculo.get('Des_Curso', [])),
            'Status': status,
            'Requisitos_Idade': 'Atende' if idade_adequada else 'Não atende',
            'Requisitos_Escolaridade': 'Atende' if escolaridade_adequada else 'Não atende',
            'Requisitos_Experiencia': 'Atende' if experiencia_adequada else 'Não atende',
            'Avaliacao_Llama': avaliacao_llama
        }
        resultados.append(resultado)

# Salvar os resultados em um arquivo CSV separado por ponto e vírgula
csv_file_path = "resultados_analise.csv"
with open(csv_file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
    fieldnames = ['Nome', 'Idade', 'Escolaridade', 'Atividades', 'Cursos', 'Status', 'Requisitos_Idade', 'Requisitos_Escolaridade', 'Requisitos_Experiencia', 'Avaliacao_Llama']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';', quoting=csv.QUOTE_MINIMAL, escapechar='\\')
    
    writer.writeheader()
    for resultado in resultados:
        writer.writerow(resultado)

print(f"Análise dos currículos concluída. Resultados salvos em {csv_file_path}")
