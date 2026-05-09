"""
VQS API Client — Connects to SOPHiA Genetics Variant Query Service.
Handles authentication, token caching, and structured variant queries.
"""

import requests
import time
import json


class VQSClient:
    """Client for the SOPHiA Genetics Variant Query Service (VQS) API."""

    IAM_URL = "https://iam-vandv.sophiagenetics.com/account/token"
    VQS_BASE = "https://platform-vandv1.sophiagenetics.com/api/variant/query"

    def __init__(self):
        self._token = None
        self._token_time = 0
        self._username = None
        self._password = None

    def authenticate(self, username, password):
        """Fetch a fresh IAM bearer token (valid ~1 hour)."""
        self._username = username
        self._password = password
        payload = {"username": username, "password": password}
        
        try:
            resp = requests.post(self.IAM_URL, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            self._token = data.get("access_token")
            self._token_time = time.time()
            return {"success": True, "token_preview": self._token[:20] + "..." if self._token else None}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def _get_token(self):
        """Return cached token, refreshing if older than 50 minutes."""
        if self._token and (time.time() - self._token_time) < 3000:
            return self._token
        if self._username and self._password:
            result = self.authenticate(self._username, self._password)
            if result["success"]:
                return self._token
        return self._token

    def _headers(self):
        token = self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
        }

    def get_schema(self, dataset_key, transformers=None, extra_params=None):
        """Fetch the column schema of a dataset."""
        params = {"key": dataset_key}
        if transformers:
            params["plan.transformers"] = transformers
        if extra_params:
            for k, v in extra_params.items():
                params[f"plan.parameters.{k}"] = v

        try:
            resp = requests.get(
                f"{self.VQS_BASE}/schema",
                params=params,
                headers=self._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            return {"success": True, "data": resp.json()}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def query_variants(self, dataset_key, columns=None, filters=None,
                       pagination=None, sorts=None, transformers=None,
                       extra_params=None):
        """
        Execute a paginated variant query against VQS.
        
        Args:
            dataset_key: The base64-encoded dataset key from Gen2 network tab
            columns: List of column expressions (default ["*"])
            filters: FQL filter string (without 'fql:' prefix)
            pagination: Dict with 'offset' and 'limit'
            sorts: List of dicts with 'column' and 'sort' keys
            transformers: Comma-separated transformer string
            extra_params: Dict of additional plan.parameters.*
        
        Returns:
            Dict with 'success', 'columns', 'data', 'total_rows'
        """
        # Build query params
        params = {"key": dataset_key, "engine.paginate": "true"}
        if transformers:
            params["plan.transformers"] = transformers
        if extra_params:
            for k, v in extra_params.items():
                params[f"plan.parameters.{k}"] = v

        # Build query body
        body = {
            "columns": columns or ["*"],
            "groupBy": ["*"],
            "filters": {"filterString": f"fql:{filters}" if filters else ""},
            "columnSorts": sorts or [],
            "pagination": pagination or {"offset": 0, "limit": 500},
        }

        try:
            resp = requests.post(
                self.VQS_BASE,
                params=params,
                json=body,
                headers=self._headers(),
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()

            page = result.get("pageContent", {})
            columns_list = page.get("columns", [])
            data_rows = page.get("data", [])

            # Convert rows to list of dicts for easier consumption
            records = []
            for row in data_rows:
                record = {}
                for i, col in enumerate(columns_list):
                    if i < len(row):
                        record[col] = row[i]
                records.append(record)

            return {
                "success": True,
                "columns": columns_list,
                "data": records,
                "raw_data": data_rows,
                "total_rows": len(data_rows),
            }
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e), "columns": [], "data": [], "total_rows": 0}

    def query_with_curl_params(self, full_url, body_json):
        """
        Execute a query using raw URL + body extracted from browser DevTools.
        This is the fastest way to replay a captured query.
        """
        try:
            resp = requests.post(
                full_url,
                json=body_json,
                headers=self._headers(),
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()
            page = result.get("pageContent", {})
            columns_list = page.get("columns", [])
            data_rows = page.get("data", [])

            records = []
            for row in data_rows:
                record = {}
                for i, col in enumerate(columns_list):
                    if i < len(row):
                        record[col] = row[i]
                records.append(record)

            return {
                "success": True,
                "columns": columns_list,
                "data": records,
                "raw_data": data_rows,
                "total_rows": len(data_rows),
            }
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def get_pathogenic_variants(self, dataset_key, transformers=None, extra_params=None):
        """
        Pre-built query: fetch Pathogenic and Likely Pathogenic variants.
        Uses ACMG classification filter.
        """
        fql = (
            '("userAnnotations.interpretation.acmg.result.classificationFinal" '
            "anyOf ('Pathogenic', 'Likely Pathogenic'))"
        )
        return self.query_variants(
            dataset_key=dataset_key,
            filters=fql,
            transformers=transformers,
            extra_params=extra_params,
        )

    def get_all_variants_scored(self, dataset_key, transformers=None, extra_params=None):
        """
        Fetch all variants with key clinical columns for priority scoring.
        Selects specific columns relevant for AI triage.
        """
        key_columns = [
            '"dynamic.sgId"',
            '"transcriptome.gene.symbol"',
            '"transcriptome.gene.code"',
            '"transcriptome.transcript.name"',
            '"short.called.variant.location.chromosome.fullSeqName"',
            '"short_predictor.inhouse.predictors.ABCD.result.label"',
            '"short.annotated.transcriptContext.transcriptVariant.cnomen.base"',
            '"short.annotated.transcriptContext.proteinVariant.pnomen.hgvsRefSeq"',
            '"short.called.alleleFrequency"',
            '"short.called.readDepth"',
            '"short.called.variant.type"',
            '"short.annotated.transcriptContext.proteinVariant.consequence.sophiaNameSelect"',
            '"short.annotated.catalogs.gnomadGenomes.global.global.value"',
            '"short.annotated.catalogs.gnomadExomes.global.global.value"',
            '"userAnnotations.interpretation.acmg.result.classificationFinal"',
            '"userAnnotations.interpretation.acmg.result.scoreFinal"',
            '"short.annotated.catalogs.clinvar.CLNSIG"',
            '"short.annotated.catalogs.clinvar.CLNREVSTAT"',
            '"userAnnotations.account.pathogenicity.level"',
            '"userAnnotations.interpretation.inReport.flagged"',
        ]
        return self.query_variants(
            dataset_key=dataset_key,
            columns=key_columns,
            transformers=transformers,
            extra_params=extra_params,
        )


# Singleton for app-wide use
vqs = VQSClient()
