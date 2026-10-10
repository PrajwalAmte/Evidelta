from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

SUPPORTED_DIMENSIONS = {
    "rate_quota",
    "tool_calling",
    "structured_output",
    "refusal_behavior",
    "latency",
    "availability",
}


@dataclass
class ProbeResult:
    provider: str
    product: str
    dimension: str
    status: str
    observed_at: str
    success_rate: float
    total_samples: int
    pass_count: int
    failure_count: int
    output: dict[str, Any] = field(default_factory=dict)
    vantage_point: dict[str, str] = field(default_factory=lambda: {"region": "us-east-1", "account_tier": "standard"})
    cost_estimate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProbeRunner:
    def __init__(self, region: str = "us-east-1", account_tier: str = "standard") -> None:
        self.vantage_point = {"region": region, "account_tier": account_tier}

    def run_probe(
        self,
        *,
        provider: str,
        product: str,
        dimension: str,
        headers: Mapping[str, Any] | None = None,
        tool_results: Sequence[bool] | None = None,
        structured_outputs: Sequence[bool] | None = None,
        refusal_responses: Sequence[str] | None = None,
        latencies_ms: Sequence[float] | None = None,
        error_rate: float | None = None,
    ) -> dict[str, Any]:
        if dimension not in SUPPORTED_DIMENSIONS:
            raise ValueError(f"Unsupported dimension: {dimension}")

        if dimension == "rate_quota":
            result = self._measure_rate_quota(provider, product, headers or {})
        elif dimension == "tool_calling":
            result = self._measure_tool_calling(provider, product, list(tool_results or []))
        elif dimension == "structured_output":
            result = self._measure_structured_output(provider, product, list(structured_outputs or []))
        elif dimension == "refusal_behavior":
            result = self._measure_refusal_behavior(provider, product, list(refusal_responses or []))
        elif dimension == "latency":
            result = self._measure_latency(provider, product, list(latencies_ms or []))
        elif dimension == "availability":
            result = self._measure_availability(provider, product, error_rate)
        else:
            raise ValueError(f"Unsupported dimension: {dimension}")

        result.vantage_point = self.vantage_point.copy()
        return result.to_dict()

    def run_suite(
        self,
        *,
        provider: str,
        product: str,
        rate_headers: Mapping[str, Any] | None = None,
        tool_results: Sequence[bool] | None = None,
        structured_outputs: Sequence[bool] | None = None,
        refusal_responses: Sequence[str] | None = None,
        latencies_ms: Sequence[float] | None = None,
        error_rate: float | None = None,
    ) -> dict[str, dict[str, Any]]:
        suite = {
            "rate_quota": self.run_probe(
                provider=provider,
                product=product,
                dimension="rate_quota",
                headers=rate_headers or {},
            ),
            "tool_calling": self.run_probe(
                provider=provider,
                product=product,
                dimension="tool_calling",
                tool_results=tool_results or [],
            ),
            "structured_output": self.run_probe(
                provider=provider,
                product=product,
                dimension="structured_output",
                structured_outputs=structured_outputs or [],
            ),
            "refusal_behavior": self.run_probe(
                provider=provider,
                product=product,
                dimension="refusal_behavior",
                refusal_responses=refusal_responses or [],
            ),
            "latency": self.run_probe(
                provider=provider,
                product=product,
                dimension="latency",
                latencies_ms=latencies_ms or [],
            ),
            "availability": self.run_probe(
                provider=provider,
                product=product,
                dimension="availability",
                error_rate=error_rate,
            ),
        }
        return suite

    def _measure_rate_quota(self, provider: str, product: str, headers: Mapping[str, Any]) -> ProbeResult:
        normalized = {str(key).lower(): str(value) for key, value in headers.items()}
        limit = self._extract_first_value(normalized, ["x-ratelimit-limit", "ratelimit-limit", "x-ratelimit-limit-day"])
        remaining = self._extract_first_value(normalized, ["x-ratelimit-remaining", "ratelimit-remaining"])
        reset = self._extract_first_value(normalized, ["x-ratelimit-reset", "ratelimit-reset"])

        if limit is None and remaining is None:
            return ProbeResult(
                provider=provider,
                product=product,
                dimension="rate_quota",
                status="not_measured",
                observed_at=datetime.now(timezone.utc).isoformat(),
                success_rate=0.0,
                total_samples=0,
                pass_count=0,
                failure_count=0,
                output={
                    "message": "No rate-limit headers were present in the observed response.",
                    "limit": None,
                    "remaining": None,
                    "reset": None,
                },
                cost_estimate=0.0,
            )

        pass_count = int(limit is not None) + int(remaining is not None)
        total_samples = 2
        failure_count = total_samples - pass_count
        success_rate = pass_count / total_samples
        status = "stable" if pass_count == 2 else "watch"
        return ProbeResult(
            provider=provider,
            product=product,
            dimension="rate_quota",
            status=status,
            observed_at=datetime.now(timezone.utc).isoformat(),
            success_rate=success_rate,
            total_samples=total_samples,
            pass_count=pass_count,
            failure_count=failure_count,
            output={
                "limit": limit,
                "remaining": remaining,
                "reset": reset,
                "headers_seen": sorted(normalized.keys()),
            },
            cost_estimate=0.02,
        )

    def _measure_tool_calling(self, provider: str, product: str, tool_results: Sequence[bool]) -> ProbeResult:
        if not tool_results:
            return ProbeResult(
                provider=provider,
                product=product,
                dimension="tool_calling",
                status="not_measured",
                observed_at=datetime.now(timezone.utc).isoformat(),
                success_rate=0.0,
                total_samples=0,
                pass_count=0,
                failure_count=0,
                output={"message": "No tool-call samples provided."},
                cost_estimate=0.04,
            )

        pass_count = sum(1 for item in tool_results if bool(item))
        total = len(tool_results)
        success_rate = pass_count / total
        status = "stable" if success_rate >= 0.9 else "degraded" if success_rate >= 0.7 else "critical"
        return ProbeResult(
            provider=provider,
            product=product,
            dimension="tool_calling",
            status=status,
            observed_at=datetime.now(timezone.utc).isoformat(),
            success_rate=success_rate,
            total_samples=total,
            pass_count=pass_count,
            failure_count=total - pass_count,
            output={"samples": [bool(item) for item in tool_results]},
            cost_estimate=0.08,
        )

    def _measure_structured_output(self, provider: str, product: str, structured_outputs: Sequence[bool]) -> ProbeResult:
        if not structured_outputs:
            return ProbeResult(
                provider=provider,
                product=product,
                dimension="structured_output",
                status="not_measured",
                observed_at=datetime.now(timezone.utc).isoformat(),
                success_rate=0.0,
                total_samples=0,
                pass_count=0,
                failure_count=0,
                output={"message": "No structured-output samples provided."},
                cost_estimate=0.05,
            )

        pass_count = sum(1 for item in structured_outputs if bool(item))
        total = len(structured_outputs)
        success_rate = pass_count / total
        status = "stable" if success_rate >= 0.97 else "watch" if success_rate >= 0.75 else "degraded"
        return ProbeResult(
            provider=provider,
            product=product,
            dimension="structured_output",
            status=status,
            observed_at=datetime.now(timezone.utc).isoformat(),
            success_rate=success_rate,
            total_samples=total,
            pass_count=pass_count,
            failure_count=total - pass_count,
            output={"samples": [bool(item) for item in structured_outputs]},
            cost_estimate=0.06,
        )

    def _measure_refusal_behavior(self, provider: str, product: str, refusal_responses: Sequence[str]) -> ProbeResult:
        if not refusal_responses:
            return ProbeResult(
                provider=provider,
                product=product,
                dimension="refusal_behavior",
                status="not_measured",
                observed_at=datetime.now(timezone.utc).isoformat(),
                success_rate=0.0,
                total_samples=0,
                pass_count=0,
                failure_count=0,
                output={"message": "No refusal prompt responses were provided."},
                cost_estimate=0.04,
            )

        refusal_patterns = ("cannot", "can’t", "won't", "unable", "not able", "i can’t", "sorry, i")
        refusal_count = 0
        cleaned = []
        for response in refusal_responses:
            lowered = str(response).lower()
            is_refusal = any(pattern in lowered for pattern in refusal_patterns)
            if is_refusal:
                refusal_count += 1
            cleaned.append({"response": response, "is_refusal": is_refusal})

        refusal_rate = refusal_count / len(refusal_responses)
        status = "stable" if refusal_rate <= 0.15 else "watch" if refusal_rate <= 0.3 else "elevated"
        return ProbeResult(
            provider=provider,
            product=product,
            dimension="refusal_behavior",
            status=status,
            observed_at=datetime.now(timezone.utc).isoformat(),
            success_rate=1.0 - refusal_rate,
            total_samples=len(refusal_responses),
            pass_count=len(refusal_responses) - refusal_count,
            failure_count=refusal_count,
            output={"refusal_rate": refusal_rate, "responses": cleaned},
            cost_estimate=0.05,
        )

    def _measure_latency(self, provider: str, product: str, latencies_ms: Sequence[float]) -> ProbeResult:
        if not latencies_ms:
            return ProbeResult(
                provider=provider,
                product=product,
                dimension="latency",
                status="not_measured",
                observed_at=datetime.now(timezone.utc).isoformat(),
                success_rate=0.0,
                total_samples=0,
                pass_count=0,
                failure_count=0,
                output={"message": "No latency samples were provided."},
                cost_estimate=0.01,
            )

        samples = [float(value) for value in latencies_ms]
        average = mean(samples)
        status = "stable" if average <= 2500 else "watch" if average <= 5000 else "degraded"
        return ProbeResult(
            provider=provider,
            product=product,
            dimension="latency",
            status=status,
            observed_at=datetime.now(timezone.utc).isoformat(),
            success_rate=1.0 if average <= 2500 else 0.5 if average <= 5000 else 0.2,
            total_samples=len(samples),
            pass_count=int(round(len(samples) * (1.0 if average <= 2500 else 0.5 if average <= 5000 else 0.2))),
            failure_count=max(len(samples) - int(round(len(samples) * (1.0 if average <= 2500 else 0.5 if average <= 5000 else 0.2))), 0),
            output={"average_ms": round(average, 2), "samples_ms": samples},
            cost_estimate=0.02,
        )

    def _measure_availability(self, provider: str, product: str, error_rate: float | None) -> ProbeResult:
        if error_rate is None:
            return ProbeResult(
                provider=provider,
                product=product,
                dimension="availability",
                status="not_measured",
                observed_at=datetime.now(timezone.utc).isoformat(),
                success_rate=0.0,
                total_samples=0,
                pass_count=0,
                failure_count=0,
                output={"message": "No availability/error-rate estimate was provided."},
                cost_estimate=0.01,
            )

        numeric_error_rate = float(error_rate)
        availability_rate = 1.0 - numeric_error_rate
        status = "stable" if availability_rate >= 0.99 else "watch" if availability_rate >= 0.95 else "degraded"
        return ProbeResult(
            provider=provider,
            product=product,
            dimension="availability",
            status=status,
            observed_at=datetime.now(timezone.utc).isoformat(),
            success_rate=availability_rate,
            total_samples=1,
            pass_count=1 if availability_rate >= 0.99 else 0,
            failure_count=1 if availability_rate < 0.99 else 0,
            output={"error_rate": round(numeric_error_rate, 4), "availability_rate": round(availability_rate, 4)},
            cost_estimate=0.01,
        )

    @staticmethod
    def _extract_first_value(headers: Mapping[str, Any], candidates: Iterable[str]) -> Any:
        for candidate in candidates:
            if candidate in headers:
                return headers[candidate]
        return None


__all__ = ["ProbeRunner", "ProbeResult", "SUPPORTED_DIMENSIONS"]
