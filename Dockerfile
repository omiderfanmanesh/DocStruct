FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONNOUSERSITE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . .

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && python -m pip install -e . \
    && mkdir -p /app/output/00_runs /app/output/01_toc /app/output/02_fixed_markdown /app/output/02_fix_reports /app/output/03_pageindex /app/output/04_answers

ENTRYPOINT ["python", "-m", "docstruct"]
CMD ["--help"]
