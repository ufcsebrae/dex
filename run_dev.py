"""Script utilitário para iniciar todo o ecossistema DEX com um único comando na porta 8081 (PEP 257)."""

import subprocess
import sys
import time
from pathlib import Path

def iniciar_ecossistema():
    raiz = Path(__file__).parent.resolve()
    pasta_web = raiz / "web"

    print("\n[DEX] Iniciando os servidores locais na porta 8081...")

    # 1. Inicia a API Python (FastAPI) na porta 8081 para evitar conflitos
    print("[1/2] Iniciando API Python em http://127.0.0.1:8081 ...")
    processo_api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api:app", "--port", "8081", "--host", "127.0.0.1"],
        cwd=raiz
    )

    time.sleep(2)

    # 2. Inicia o Frontend (Vite/React) na porta 5173
    print("[2/2] Iniciando Frontend React em http://localhost:5173 ...")
    processo_web = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=pasta_web,
        shell=True
    )

    print("\n🚀 TODO O ECOSSISTEMA ESTÁ ATIVO!")
    print("• Frontend: http://localhost:5173")
    print("• API de Dados: http://127.0.0.1:8081")
    print("\nPara encerrar ambos os servidores, pressione CTRL+C neste terminal.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[DEX] Desligando os servidores de forma segura...")
        processo_api.terminate()
        processo_web.terminate()

if __name__ == "__main__":
    iniciar_ecossistema()
