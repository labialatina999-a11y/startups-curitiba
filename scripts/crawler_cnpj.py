import csv
import json
import os
import time
import requests

# Caminhos dos arquivos (considerando que o script roda na raiz ou via automação)
ARQUIVO_ENTRADA_CSV = 'dados_cnpjs.csv'   # Sua lista de entrada exportada em CSV
ARQUIVO_SAIDA_JSON = 'startups_data.json' # O arquivo que alimenta seu mapa diretamente

def consultar_cnpj(cnpj):
    """Consulta dados públicos do CNPJ via BrasilAPI"""
    cnpj_limpo = cnpj.replace('.', '').replace('/', '').replace('-', '')
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        print(f"[-] Erro {response.status_code} no CNPJ: {cnpj}")
        return None
    except Exception as e:
        print(f"[-] Falha de conexão no CNPJ {cnpj}: {e}")
        return None

def obter_coordenadas(logradouro, numero, bairro, municipio, estado):
    """
    Busca a geolocalização gratuita (via Nominatim/OpenStreetMap).
    Mapeia o endereço para Latitude e Longitude exatas.
    """
    endereco_completo = f"{logradouro}, {numero} - {bairro}, {municipio} - {estado}, Brasil"
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'MapeadorStartupsPR/1.0'}
    params = {'q': endereco_completo, 'format': 'json', 'limit': 1}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200 and len(response.json()) > 0:
            resultado = response.json()[0]
            return float(resultado['lat']), float(resultado['lon'])
    except Exception as e:
        print(f"[-] Erro ao geolocalizar endereço: {e}")
    return -25.4296, -49.2719 # Coordenadas centrais de Curitiba caso falhe

def processar_carga():
    print("[*] Iniciando o processamento dos CNPJs...")
    startups_mapeadas = []

    # Se já existir o arquivo JSON do mapa, carrega os dados atuais para não perder nada
    if os.path.exists(ARQUIVO_SAIDA_JSON):
        try:
            with open(ARQUIVO_SAIDA_JSON, 'r', encoding='utf-8') as f:
                startups_mapeadas = json.load(f)
        except:
            startups_mapeadas = []

    # Cria uma lista de CNPJs que já foram processados antes para evitar consultas repetidas
    cnpjs_existentes = {item.get('cnpj') for item in startups_mapeadas if 'cnpj' in item}

    if not os.path.exists(ARQUIVO_ENTRADA_CSV):
        print(f"[-] Erro: O arquivo {ARQUIVO_ENTRADA_CSV} não foi encontrado na raiz.")
        return

    with open(ARQUIVO_ENTRADA_CSV, mode='r', encoding='utf-8') as f_in:
        # Lê o CSV usando ponto e vírgula como separador padrão das planilhas
        leitor = csv.DictReader(f_in, delimiter=';') 
        
        for row in leitor:
            cnpj = row.get('CNPJ')
            if not cnpj:
                continue
                
            cnpj = cnpj.strip()
            if cnpj in cnpjs_existentes:
                continue
            
            print(f"[+] Buscando dados para o CNPJ: {cnpj}")
            dados_api = consultar_cnpj(cnpj)
            
            if dados_api:
                logradouro = dados_api.get('logradouro', '')
                numero = dados_api.get('numero', '')
                bairro = dados_api.get('bairro', '')
                municipio = dados_api.get('municipio', '')
                estado = dados_api.get('uf', '')
                
                # Descobre as coordenadas exatas para plotar o alfinete no mapa
                lat, lon = obter_coordenadas(logradouro, numero, bairro, municipio, estado)
                
                nova_startup = {
                    "cnpj": cnpj,
                    "razao_social": dados_api.get('razao_social'),
                    "nome_fantasia": dados_api.get('nome_fantasia') or row.get('Razão Social') or dados_api.get('razao_social'),
                    "status_mapeamento": row.get('Status', 'Aprovada'), 
                    "contatos": {
                        "email": dados_api.get('email', ''),
                        "telefone": f"({dados_api.get('ddd_telefone_1', '')[:2]}) {dados_api.get('ddd_telefone_1', '')[2:]}" if dados_api.get('ddd_telefone_1') else ''
                    },
                    "localizacao": {
                        "logradouro": logradouro,
                        "numero": numero,
                        "bairro": bairro,
                        "cep": dados_api.get('cep', ''),
                        "municipio": municipio,
                        "estado": estado,
                        "latitude": lat,
                        "longitude": lon
                    },
                    "situacao_cadastral": dados_api.get('descricao_situacao_cadastral', 'ATIVA')
                }
                
                startups_mapeadas.append(nova_startup)
                # Pausa estratégica para não estourar o limite das APIs públicas gratuitas
                time.sleep(2.0) 
                
    # Salva ou atualiza o arquivo JSON oficial do mapa interativo
    with open(ARQUIVO_SAIDA_JSON, 'w', encoding='utf-8') as f_out:
        json.dump(startups_mapeadas, f_out, indent=4, ensure_ascii=False)
    
    print(f"[+] Processo finalizado! O arquivo {ARQUIVO_SAIDA_JSON} foi devidamente atualizado.")

if __name__ == '__main__':
    processar_carga()
