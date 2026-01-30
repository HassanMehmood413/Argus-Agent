import httpx
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


class PrometheusClient:
    """
    Client for querying Prometheus metrics.
    """
    
    def __init__(self, base_url: str = "http://prometheus:9090"):
        self.base_url = base_url.rstrip("/")
    
    async def query(self, promql: str) -> Dict[str, Any]:
        """
        Run an instant query.
        
        Args:
            promql: PromQL query string
        
        Returns:
            Query result
        
        Example:
            result = await client.query('up{service="api-gateway"}')
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/query",
                params={"query": promql},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def query_range(
        self, 
        promql: str, 
        start: datetime = None,
        end: datetime = None,
        step: str = "1m"
    ) -> Dict[str, Any]:
        """
        Run a range query (time series).
        
        Args:
            promql: PromQL query
            start: Start time (default: 1 hour ago)
            end: End time (default: now)
            step: Resolution step
        
        Returns:
            Time series data
        """
        if end is None:
            end = datetime.utcnow()
        if start is None:
            start = end - timedelta(hours=1)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/query_range",
                params={
                    "query": promql,
                    "start": start.timestamp(),
                    "end": end.timestamp(),
                    "step": step
                },
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def get_service_metrics(
        self, 
        service: str, 
        namespace: str
    ) -> Dict[str, Any]:
        """
        Get common metrics for a service.
        
        This runs multiple queries and combines results.
        """
        metrics = {}
        
        # CPU Usage
        try:
            result = await self.query(
                f'rate(container_cpu_usage_seconds_total{{namespace="{namespace}", pod=~"{service}.*"}}[5m]) * 100'
            )
            values = self._extract_values(result)
            metrics["cpu_usage_percent"] = sum(values) / len(values) if values else 0
        except Exception as e:
            metrics["cpu_usage_percent"] = None
            metrics["cpu_error"] = str(e)
        
        # Memory Usage
        try:
            result = await self.query(
                f'container_memory_usage_bytes{{namespace="{namespace}", pod=~"{service}.*"}}'
            )
            values = self._extract_values(result)
            metrics["memory_usage_bytes"] = sum(values)
            
            # Also get memory limit for percentage
            limit_result = await self.query(
                f'container_spec_memory_limit_bytes{{namespace="{namespace}", pod=~"{service}.*"}}'
            )
            limits = self._extract_values(limit_result)
            if limits and sum(limits) > 0:
                metrics["memory_usage_percent"] = (sum(values) / sum(limits)) * 100
        except Exception as e:
            metrics["memory_usage_bytes"] = None
            metrics["memory_error"] = str(e)
        
        # Error Rate (if using standard HTTP metrics)
        try:
            # Total requests
            total = await self.query(
                f'sum(rate(http_requests_total{{namespace="{namespace}", service="{service}"}}[5m]))'
            )
            # Error requests (5xx)
            errors = await self.query(
                f'sum(rate(http_requests_total{{namespace="{namespace}", service="{service}", status=~"5.."}}[5m]))'
            )
            
            total_val = self._extract_single_value(total)
            error_val = self._extract_single_value(errors)
            
            if total_val and total_val > 0:
                metrics["request_rate_per_second"] = total_val
                metrics["error_rate_percent"] = (error_val / total_val) * 100 if error_val else 0
            else:
                metrics["request_rate_per_second"] = 0
                metrics["error_rate_percent"] = 0
        except Exception as e:
            metrics["error_rate_error"] = str(e)
        
        # Latency P99
        try:
            result = await self.query(
                f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{namespace="{namespace}", service="{service}"}}[5m])) by (le))'
            )
            metrics["latency_p99_seconds"] = self._extract_single_value(result)
        except Exception as e:
            metrics["latency_error"] = str(e)
        
        return metrics
    
    def _extract_values(self, result: Dict) -> List[float]:
        """Extract numeric values from Prometheus response."""
        values = []
        data = result.get("data", {}).get("result", [])
        for item in data:
            val = item.get("value", [None, None])[1]
            if val and val != "NaN":
                values.append(float(val))
        return values
    
    def _extract_single_value(self, result: Dict) -> Optional[float]:
        """Extract single value from Prometheus response."""
        values = self._extract_values(result)
        return values[0] if values else None


