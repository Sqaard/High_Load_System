FROM node:latest

WORKDIR /app

# Install curl for healthchecks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 80

# Run Vite on 0.0.0.0 for Docker accessibility
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]