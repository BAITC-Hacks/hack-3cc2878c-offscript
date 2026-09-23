# Build context = repo root
FROM node:20-alpine AS build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci || npm install
COPY frontend ./
COPY shared/mocks /app/shared/mocks
ARG VITE_API_URL=http://127.0.0.1:8000
ARG VITE_USE_MOCKS=0
ENV VITE_API_URL=$VITE_API_URL VITE_USE_MOCKS=$VITE_USE_MOCKS
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
