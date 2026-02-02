FROM python:3.12-alpine

RUN apk add --no-cache openssh bash coreutils ca-certificates ncurses shadow \
    && adduser -D -s /bin/sh put \
    && adduser -D -s /bin/sh get \
    # set random passwords so accounts aren't "locked" (password auth stays disabled in sshd_config)
    && (head -c 32 /dev/urandom | base64 | tr -d '\n' | sed 's/^/put:/' | chpasswd) \
    && (head -c 32 /dev/urandom | base64 | tr -d '\n' | sed 's/^/get:/' | chpasswd) \
    && mkdir -p /var/run/sshd /etc/ssh /data /keys \
    && chmod 755 /data

WORKDIR /srv

COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY sshd_config /etc/ssh/sshd_config
COPY entrypoint.sh /entrypoint.sh
COPY app /srv/app

RUN chmod +x /entrypoint.sh \
    && chmod +x /srv/app/poc_gateway.py \
    && chmod +x /srv/app/authorize_keys.sh \
    && chmod +x /srv/app/poc_gateway_wrapper.sh

EXPOSE 22
ENTRYPOINT ["/entrypoint.sh"]
