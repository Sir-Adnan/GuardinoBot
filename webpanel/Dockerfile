# --- build the SPA ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
# npm ci = deterministic install from the committed lockfile (reproducible
# builds); falls back to npm install if the lockfile is missing/out of sync.
RUN npm ci || npm install
COPY . .
RUN npm run build

# --- serve with nginx ---
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Template, not conf.d: the official entrypoint envsubst's ONLY defined env
# vars (API_UPSTREAM below) into /etc/nginx/conf.d — nginx runtime vars like
# $uri/$host are untouched. Lets multi-bot installs point each panel at its
# own api container (see nginx.conf comment).
COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV API_UPSTREAM=api:8000
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
