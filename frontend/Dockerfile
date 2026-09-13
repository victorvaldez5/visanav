# Stage 1: build: get version of node with OpenSSL
FROM node:20-bullseye-slim AS build

WORKDIR /app

COPY ./frontend/package.json ./frontend/package-lock.json ./

RUN npm ci

COPY ./frontend ./app

EXPOSE 3000

CMD ["npm", "run", "dev"]
