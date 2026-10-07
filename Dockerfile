FROM python:3.11-slim
WORKDIR /app
COPY Code/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY Code /app/Code
COPY Model_Prompts_Config /app/Model_Prompts_Config
COPY Input_Data /app/Input_Data
ENV PYTHONPATH=/app/Code/src HLD_DATA_DIR=/data
EXPOSE 8000 8501
CMD ["uvicorn", "hldrag.api:app", "--host", "0.0.0.0", "--port", "8000"]
