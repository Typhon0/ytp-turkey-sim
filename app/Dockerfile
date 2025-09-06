FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# ----- 1. Dépendances système -----
RUN apt-get update && apt-get install -y --no-install-recommends \
       wget curl gnupg ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

# ----- 2. Dépôt officiel Mozilla + Firefox (ESR) -----
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/mozilla.gpg] \
        https://packages.mozilla.org/apt mozilla main" \
        | tee /etc/apt/sources.list.d/mozilla.list \
 && curl -fsSL https://packages.mozilla.org/apt/repo-signing-key.gpg \
        | gpg --dearmor -o /usr/share/keyrings/mozilla.gpg \
 && apt-get update \
 && apt-get install -y --no-install-recommends firefox-esr \
 && rm -rf /var/lib/apt/lists/*

# ----- 3. Geckodriver (version correspondant à Firefox ESR) -----
ARG GECKO_VER=0.34.0
RUN curl -fsSL \
      "https://github.com/mozilla/geckodriver/releases/download/v${GECKO_VER}/geckodriver-v${GECKO_VER}-linux64.tar.gz" \
      -o /tmp/gd.tar.gz \
 && tar -xzf /tmp/gd.tar.gz -C /usr/local/bin \
 && chmod +x /usr/local/bin/geckodriver \
 && rm /tmp/gd.tar.gz

# ----- 4. Python deps & applis -----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY youtube_cookie_simulator.py .
COPY setup_cookies_headless.py .
RUN mkdir -p /app/cookies

CMD ["python", "youtube_cookie_simulator.py"]
