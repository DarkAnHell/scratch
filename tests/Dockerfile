FROM python:3.12-alpine

RUN apk add --no-cache openssh-client bash coreutils netcat-openbsd
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY run_tests.sh /app/run_tests.sh
COPY test_system.py /app/test_system.py

RUN chmod +x /app/run_tests.sh