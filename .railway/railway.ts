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
    source: github("victorvaldez5/visanav", { checkSuites: false }),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/scrapers/uscis_scraper/Dockerfile" },
    replicas: { "us-east4-eqdc4a": 1 },
    deploy: { cronSchedule: "0 6 * * 1", restartPolicyType: "NEVER" },
    env: { AWS_ACCESS_KEY_ID: preserve(), AWS_ENDPOINT_URL: preserve(), AWS_REGION_NAME: preserve(), AWS_SECRET_ACCESS_KEY: preserve(), R2_BUCKET: preserve() },
  });
  // One cron service per scrape source, all built from the same scraper image; the
  // start command picks the spider (the image's default command crawls USCIS).
  // Schedules are staggered after the USCIS crawl (Mondays 06:00 UTC, about 2 hours).
  // Each new service needs the same R2 variables as visanav-scraper set on Railway.
  const scraperSource = (name: string, spider: string, cronSchedule: string) =>
    service(name, {
      source: github("victorvaldez5/visanav", { checkSuites: false }),
      build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/scrapers/uscis_scraper/Dockerfile" },
      replicas: { "us-east4-eqdc4a": 1 },
      deploy: { startCommand: `scrapy crawl ${spider}`, cronSchedule, restartPolicyType: "NEVER" },
      env: { AWS_ACCESS_KEY_ID: preserve(), AWS_ENDPOINT_URL: preserve(), AWS_REGION_NAME: preserve(), AWS_SECRET_ACCESS_KEY: preserve(), R2_BUCKET: preserve() },
    });
  const visanavScraperEcfr = scraperSource("visanav-scraper-ecfr", "ecfr", "0 9 * * 1");
  const visanavScraperFederalRegister = scraperSource("visanav-scraper-federal-register", "federal-register", "30 9 * * 1");
  // Scheduled ingestion: every hour, `manage.py refresh_corpus` ingests whatever is due
  // (a scrape source whose crawl left a new feed in R2, or curated data/ changed by a
  // deploy) and exits in seconds when nothing is. It runs the API code against the same
  // database, so it needs the API's Django and Postgres variables, VOYAGE_API_KEY, and
  // read-only credentials for the bucket the scrapers write to.
  const visanavIngest = service("visanav-ingest", {
    source: github("victorvaldez5/visanav", { checkSuites: false }),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/api/ingest.Dockerfile" },
    replicas: { "ams": 1 },
    deploy: { cronSchedule: "15 * * * *", restartPolicyType: "NEVER" },
    env: { ALLOWED_HOSTS: preserve(), AWS_ACCESS_KEY_ID: preserve(), AWS_ENDPOINT_URL: preserve(), AWS_REGION_NAME: preserve(), AWS_SECRET_ACCESS_KEY: preserve(), CONVERSATION_ENCRYPTION_KEYS: preserve(), DJANGO_SECRET_KEY: preserve(), DJANGO_SETTINGS_MODULE: preserve(), POSTGRES_DB: preserve(), POSTGRES_HOST: preserve(), POSTGRES_PASSWORD: preserve(), POSTGRES_PORT: preserve(), POSTGRES_SSLMODE: preserve(), POSTGRES_USER: preserve(), R2_BUCKET: preserve(), VOYAGE_API_KEY: preserve() },
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
    resources: [visanavScraper, visanavScraperEcfr, visanavScraperFederalRegister, visanavIngest, visanav],
  });
});
