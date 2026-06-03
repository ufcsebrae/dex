#%%
import logging
import sys
from datetime import datetime
from pathlib import Path

def configura_logger(nome_logger: str) -> logging.Logger:
    """
    Constrói e retorna um logger estruturado em conformidade com a PEP 282.
    Otimizado com pathlib e Walrus Operator (PEP 572) para I/O.
    """
    # PEP 572: Walrus Operator para atribuição e verificação simultânea
    if not (log_dir := Path("logs")).exists():
        log_dir.mkdir(parents=True, exist_ok=True)

    # Geração de artefato temporal 
    current_date: str = datetime.now().strftime("%d-%m-%Y")
    log_file: Path = log_dir / f"logs_{current_date}.log"
    formato_log: str = "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s"

    logging.basicConfig(
        level=logging.INFO,
        format=formato_log,
        datefmt="%d-%m-%Y %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )

    return logging.getLogger(nome_logger)
