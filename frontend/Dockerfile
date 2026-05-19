FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build


FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/conf.d/default.conf.template

# Default backend host — override with BACKEND_HOST env var in production
ENV BACKEND_HOST=backend

EXPOSE 80

# envsubst replaces only ${BACKEND_HOST}, leaving nginx variables ($host etc.) intact
CMD ["/bin/sh", "-c", "envsubst '${BACKEND_HOST}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
