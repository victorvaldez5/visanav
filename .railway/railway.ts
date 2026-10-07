import { defineRailway, github, preserve, project, service } from "railway/iac";

// Railway Infrastructure as Code for the services built from this repo. It replaces
// railway.json / railway.toml (Config as Code), which Railway stops honoring on
// 2026-12-01. Do not reintroduce a root railway.json: it applied to every service built
// from this repo and made the scraper build api/Dockerfile.
//
// Postgres and its volume are deliberately NOT declared here, so a plan or apply from
// this file never touches the database.
//
// `partial` marks this file as managing only the resources it lists; other resources in
// the environment are left alone. Always run `railway config plan` and read it before
// `railway config apply`. Secrets stay on Railway as preserve(); never inline values.
export const partial = "visanav";

export default defineRailway(() => {
  const visanavScraper = service("visanav-scraper", {
    source: github("victorvaldez5/visanav", { branch: "feat/scraper-railway-migration", checkSuites: false }),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/scrapers/uscis_scraper/Dockerfile" },
    replicas: { "us-east4-eqdc4a": 1 },
    deploy: { cronSchedule: "0 6 * * 1", restartPolicyType: "NEVER" },
    env: { AWS_ACCESS_KEY_ID: preserve(), AWS_ENDPOINT_URL: preserve(), AWS_REGION_NAME: preserve(), AWS_SECRET_ACCESS_KEY: preserve(), R2_BUCKET: preserve() },
  });
  const visanav = service("visanav", {
    source: github("victorvaldez5/visanav", { checkSuites: true }),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "./api/Dockerfile" },
    preDeploy: "python manage.py migrate --noinput",
    replicas: { "ams": 1 },
    deploy: { sleepApplication: true, restartPolicyType: "ON_FAILURE", restartPolicyMaxRetries: 3 },
    domains: [{ domain: "api.visanav.org", port: 8000 }],
    networking: { privateNetworkEndpoint: "api-frosty-rain-5363" },
    env: { ALLOWED_HOSTS: preserve(), ANTHROPIC_API_KEY: preserve(), CONVERSATION_ENCRYPTION_KEYS: preserve(), CSRF_TRUSTED_ORIGINS: preserve(), DJANGO_SECRET_KEY: preserve(), DJANGO_SETTINGS_MODULE: preserve(), FRONTEND_URL: preserve(), KNOWLEDGE_DATA_DIR: preserve(), LLM_PROVIDER: preserve(), PORT: preserve(), POSTGRES_DB: preserve(), POSTGRES_HOST: preserve(), POSTGRES_PASSWORD: preserve(), POSTGRES_PORT: preserve(), POSTGRES_SSLMODE: preserve(), POSTGRES_USER: preserve(), SECURE_SSL_REDIRECT: preserve(), SEED_DIRECTORY: preserve(), SKIP_MIGRATE_ON_START: preserve(), TURNSTILE_SECRET_KEY: preserve(), VOYAGE_API_KEY: preserve() },
  });

  return project("jubilant-success", {
    resources: [visanavScraper, visanav],
  });
});
