# T21 feasibility: DeepSeek Harness runs only in this image.
# Pinned: dsh 0.2.1-rc.2 (source tag dsh-v0.2.1-rc.2 = 687f282e8625c6b8d11ff58211a90524be2e4317).
# Nothing from the eval repo, runs/, runs-raw/ or the data directory is copied in or mounted.
# DEEPSEEK_API_KEY is passed only at `docker run -e`; never baked into the image.
FROM node:22-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/dsh
COPY package.json ./
RUN npm install --no-audit --no-fund \
 && npx dsh --version > /opt/dsh/DSH_VERSION

RUN mkdir -p /work /home/node/dsh-home && chown -R node:node /work /home/node/dsh-home
USER node
ENV DSH_HOME=/home/node/dsh-home PATH=/opt/dsh/node_modules/.bin:$PATH
WORKDIR /work
CMD ["dsh", "--version"]
