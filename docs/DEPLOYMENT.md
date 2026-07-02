# Déploiement VPS

Sous-domaine retenu pour le MVP :

```text
https://abf.finablasolution.com
```

## Pré-requis DNS

Créer / vérifier un record A :

```text
abf.finablasolution.com  A  76.13.129.252
```

Si Hostinger affiche aussi `2.57.91.91`, supprimer ce record parking.

## Commandes production

```bash
cd /opt/finab-abf-assistant
docker compose -f docker-compose.prod.yml up -d --build
```

## Vérifications

```bash
docker ps | grep finab-abf-assistant
curl -s http://127.0.0.1:8080/health
curl -skI https://abf.finablasolution.com
```
