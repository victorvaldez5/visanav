FROM public.ecr.aws/glue/aws-glue-libs:5 AS builder

USER root

WORKDIR /home/hadoop/workspace

RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels \
    beautifulsoup4 pypdf pypdf[crypto] nltk pinecone python-dotenv

###############################################################################
# 2) DEVELOPMENT: inherits from builder, adds dev-dependencies & drops to shell
###############################################################################
FROM builder AS development

COPY --from=builder /wheels /wheels

RUN pip install --no-cache-dir /wheels/*.whl

# Download punkt into /usr/local/share/nltk_data
RUN python -m nltk.downloader -d /usr/local/share/nltk_data punkt punkt_tab

ENV NLTK_DATA=/usr/local/share/nltk_data

USER hadoop

###############################################################################
# 3) PRODUCTION: install wheel and zip dependencies to add upload to s3
###############################################################################
FROM builder AS production

COPY --from=builder /wheels /wheels

RUN pip install --no-cache-dir /wheels/*.whl -t ./dependencies

# add dependencies to python path
ENV PYTHONPATH=/home/hadoop/workspace/dependencies:$PYTHONPATH

# Download punkt into dependencies/nltk_data
RUN mkdir -p ./dependencies/nltk_data
RUN python3 -m nltk.downloader -d /home/hadoop/workspace/dependencies/nltk_data punkt punkt_tab


RUN zip -r ./vendor.zip ./dependencies
