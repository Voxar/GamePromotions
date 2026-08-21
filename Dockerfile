FROM python:3.13-slim

# supercronic rather than cron: runs in the foreground (so Coolify sees a healthy
# long-running process), logs jobs to stdout, inherits the container env, and
# needs no root.
ARG TARGETARCH=amd64
ARG SUPERCRONIC_VERSION=v0.2.49
ADD https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${TARGETARCH} /usr/local/bin/supercronic
COPY deploy/supercronic.sha1 /tmp/supercronic.sha1
RUN grep " supercronic-linux-${TARGETARCH}\$" /tmp/supercronic.sha1 \
      | sed "s| supercronic-linux-${TARGETARCH}\$|  /usr/local/bin/supercronic|" \
      | sha1sum -c - \
    && chmod 0755 /usr/local/bin/supercronic \
    && rm /tmp/supercronic.sha1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py crontab ./
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY models/ models/
COPY sources/ sources/
COPY destinations/ destinations/
COPY databases/ databases/

RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh \
    && useradd -m appuser \
    && chown -R appuser /app
USER appuser

# Unbuffered so job output reaches `coolify app-logs` as it happens.
ENV PYTHONUNBUFFERED=1

CMD ["docker-entrypoint.sh"]
