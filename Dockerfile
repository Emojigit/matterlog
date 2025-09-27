FROM python:3.13-alpine

COPY matterlog.py /app/matterlog.py
COPY LICENSE.md /app/LICENSE.md
COPY COPYING.txt /app/COPYING.txt
COPY requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip install -r requirements.txt && rm requirements.txt

VOLUME ["/app/logs"]

CMD ["python", "matterlog.py"]