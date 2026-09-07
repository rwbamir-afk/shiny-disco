# Build the Mini App and serve the static bundle.
# The app talks to the backend via VITE_API_URL (e.g. https://api.example.com).
FROM node:20-alpine AS build
WORKDIR /app
COPY apps/mini-app/package.json ./
RUN npm install
COPY apps/mini-app .
RUN VITE_API_URL=${VITE_API_URL:-} npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
