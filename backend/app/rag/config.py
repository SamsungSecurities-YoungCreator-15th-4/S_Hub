# 회의 후 확정 — 값은 환경변수로 주입하고, 미설정 시 아래 기본값을 사용한다.
import os

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "")  # 회의 후 확정 (예: "text-embedding-3-small")
# 엔진(engine/rag/ingest.py)에도 같은 이름의 상수가 있고 값은 1000 **문자** / 200 문자다.
# 단위가 다른 것이 의도된 선택이라 맞추지 않는다 — 여기는 임베딩 모델의 토큰 입력
# 한도가 기준이고, 엔진은 재현성 때문에 tiktoken 버전과 무관한 문자 기준을 쓴다.
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))    # 회의 후 확정 (토큰 단위)
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))  # 회의 후 확정 (토큰 단위)
TOP_K = int(os.getenv("TOP_K", "5"))                # 회의 후 확정
LLM_MODEL = os.getenv("LLM_MODEL", "")              # 회의 후 확정 (예: "gpt-4o")
