FROM node:24.19.0-alpine@sha256:d32cdf619f63fe0471182d08996dd516c6275bb5fd31ae06e55a570bd9e1ad43 AS build
WORKDIR /srv/chatsar
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
RUN npm run typecheck && npm run build

FROM nginxinc/nginx-unprivileged:1.30.2-alpine@sha256:de3e40ec8b7debd7194fc798d4bbfb102c7f8b012b2c73032816b5f72393acdd
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /srv/chatsar/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
