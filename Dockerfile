FROM waggle/plugin-base:1.1.1-base

COPY requirements.txt /app/
RUN pip3 install --no-cache-dir --upgrade -r /app/requirements.txt

COPY . /app/
WORKDIR /app

ENTRYPOINT ["python3", "/app/main.py"]
