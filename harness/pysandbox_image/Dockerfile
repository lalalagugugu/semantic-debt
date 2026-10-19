# T21 planning agent: the Python sandbox. One fresh container per execution; the harness
# runs it by image ID and only with the argv built by harness/pysandbox.py (no volume, no
# network, read-only root, no capabilities). Data reaches the code only through stdin, as
# the rows run_sql returned. The 30-second limit lives here, so the harness never needs any
# docker command other than `docker run`.
FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

RUN pip install --no-cache-dir pandas==2.3.3 numpy==2.3.4

COPY runner.py /sandbox/runner.py
USER 10001:10001
WORKDIR /tmp
ENTRYPOINT ["timeout", "-s", "KILL", "30", "python", "-I", "/sandbox/runner.py"]
