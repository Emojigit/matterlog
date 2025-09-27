FROM python:3.13-alpine

COPY requirements.txt /app/requirements.txt
RUN cd /app && pip install -r requirements.txt && rm requirements.txt

COPY matterlog.py /app/matterlog.py
COPY LICENSE.md /app/LICENSE.md
COPY COPYING.txt /app/COPYING.txt

WORKDIR /app
VOLUME ["/app/logs"]
CMD ["python", "matterlog.py"]