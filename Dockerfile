FROM busybox:1.36.1 AS assets
LABEL maintainer="Joel Montes de Oca <joelmontesdeoca@proton.me>"

WORKDIR /app

# Minimal assets stage for backend-only deployments.
# Creates the expected /app/public directory so later stages can COPY it.
RUN mkdir -p /app/public

CMD ["true"]

###############################################################################

FROM python:3.14.3-slim AS app-build
LABEL maintainer="Joel Montes de Oca <joelmontesdeoca@proton.me>"

WORKDIR /app

ARG APP_UID=1000
ARG APP_GID=1000

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man \
  && apt-get clean \
  && groupadd -g "${APP_GID}" python \
  && useradd --create-home --no-log-init -u "${APP_UID}" -g "${APP_GID}" python \
  && chown python:python -R /app

USER python

COPY --chown=python:python pyproject.toml ./
COPY --chown=python:python bin/ ./bin

ENV PYTHONUNBUFFERED="true" \
  PYTHONPATH="." \
  PATH="${PATH}:/home/python/.local/bin" \
  USER="python"

# ORIGINAL — replaced by: switched to pip install for pyproject.toml dependencies
# RUN chmod 0755 bin/* && bin/uv-install

# UPDATED — install dependencies using pip
RUN pip install --upgrade pip setuptools
RUN pip install .

# CHANGE LOG
# Changed by : Copilot
# Date       : 2026-03-17
# Reason     : Removed uv-install step, switched to pip install for pyproject.toml dependencies.
# Impact     : Python dependencies now installed via pip, uv not required, build step simplified.

CMD ["bash"]

###############################################################################

FROM python:3.14.3-slim AS app
LABEL maintainer="Joel Montes de Oca <joelmontesdeoca@proton.me>"

WORKDIR /app

ARG APP_UID=1000
ARG APP_GID=1000

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl libpq5 \
  libjpeg62-turbo libfreetype6 liblcms2-2 libwebp-dev libopenjp2-7 zlib1g \
  && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man \
  && apt-get clean \
  && groupadd -g "${APP_GID}" python \
  && useradd --create-home --no-log-init -u "${APP_UID}" -g "${APP_GID}" python \
  && mkdir -p /public_collected public \
  && chown python:python -R /public_collected /app

USER python

ARG DEBUG="false"
ENV DEBUG="${DEBUG}" \
  PYTHONUNBUFFERED="true" \
  PYTHONPATH="." \
  PATH="${PATH}:/home/python/.local/bin" \
  USER="python"

COPY --chown=python:python --from=assets /app/public /public
COPY --chown=python:python --from=app-build /home/python/.local /home/python/.local
COPY --chown=python:python . .

WORKDIR /app/src

RUN if [ "${DEBUG}" = "false" ]; then \
  SECRET_KEY=dummyvalue python3 manage.py collectstatic --no-input; \
  else mkdir -p /app/public_collected; fi

ENTRYPOINT ["/app/bin/docker-entrypoint-web"]

EXPOSE 8000

CMD ["gunicorn", "-c", "python:config.gunicorn", "config.wsgi"]
