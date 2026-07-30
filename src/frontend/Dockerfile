# --- stage 1: build bằng Vite ---
FROM node:20-alpine AS build

WORKDIR /app

# Vite thay thế import.meta.env LÚC BUILD, nên hai biến này phải là build args.
# Truyền qua `environment` của container sẽ không có tác dụng gì.
ARG VITE_API_URL=""
ARG VITE_AGENT_URL="/agent/test-drive"
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_AGENT_URL=$VITE_AGENT_URL

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# --- stage 2: phục vụ tĩnh bằng nginx ---
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
