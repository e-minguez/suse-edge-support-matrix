FROM registry.suse.com/bci/python:3.12

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY support-matrix.py .

ENTRYPOINT ["python3", "support-matrix.py"]