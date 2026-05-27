#!/usr/bin/env python3
"""Generate multi-service traces via OTLP gRPC to Jaeger (port 4317).

Sends spans with recorded durations — no actual sleeping needed.
"""
import argparse
import random
import time

from opentelemetry import trace as otel_trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

SERVICES = [
    "frontend",
    "cartservice",
    "redis-cart",
    "productcatalogservice",
    "checkoutservice",
    "shippingservice",
    "emailservice",
    "currencyservice",
    "paymentservice",
    "recommendationservice",
    "adservice",
]

CALL_GRAPH = {
    "frontend": ["cartservice", "productcatalogservice", "checkoutservice", "recommendationservice"],
    "cartservice": ["redis-cart"],
    "productcatalogservice": ["adservice"],
    "checkoutservice": ["shippingservice", "paymentservice", "currencyservice", "emailservice"],
    "shippingservice": ["emailservice"],
}

AVERAGE_LATENCY_MS = {
    ("frontend", "cartservice"): 45,
    ("frontend", "productcatalogservice"): 30,
    ("frontend", "checkoutservice"): 60,
    ("frontend", "recommendationservice"): 25,
    ("cartservice", "redis-cart"): 5,
    ("checkoutservice", "shippingservice"): 80,
    ("checkoutservice", "paymentservice"): 120,
    ("checkoutservice", "emailservice"): 200,
    ("checkoutservice", "currencyservice"): 50,
    ("shippingservice", "emailservice"): 120000,
    ("productcatalogservice", "adservice"): 20,
}


def setup_tracers(otlp_endpoint: str = "http://localhost:4317"):
    tracers = {}
    for svc in SERVICES:
        resource = Resource.create({SERVICE_NAME: svc})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        tracers[svc] = otel_trace.get_tracer(svc, tracer_provider=provider)
    return tracers


def build_service_path():
    path = ["frontend"]

    if random.random() < 0.8:
        path.append("cartservice")
        if random.random() < 0.7:
            path.append("redis-cart")

    if random.random() < 0.6:
        path.append("productcatalogservice")
        if random.random() < 0.3:
            path.append("adservice")

    if random.random() < 0.4:
        path.append("recommendationservice")

    if random.random() < 0.3:
        path.append("checkoutservice")
        if random.random() < 0.8:
            path.append("shippingservice")
            if random.random() < 0.5:
                path.append("emailservice")
        if random.random() < 0.6:
            path.append("paymentservice")
        if random.random() < 0.4:
            path.append("currencyservice")

    return path


def generate_trace(tracers: dict, trace_num: int, anomaly_rate: float):
    path = build_service_path()

    root_tracer = tracers["frontend"]
    root_span = root_tracer.start_span(f"GET /product/{trace_num}")
    ctx = otel_trace.set_span_in_context(root_span)

    for prev_svc, svc in zip(path, path[1:]):
        tracer = tracers.get(svc)
        if tracer is None:
            continue

        edge = (prev_svc, svc)
        base_ms = AVERAGE_LATENCY_MS.get(edge, random.uniform(10, 100))

        if random.random() < anomaly_rate:
            base_ms *= random.uniform(5, 15)

        span = tracer.start_span(f"{svc}.handle", context=ctx)
        if random.random() < anomaly_rate * 0.3:
            span.set_attribute("error", True)

        span.end()
        ctx = otel_trace.set_span_in_context(span)

    root_span.end()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--anomaly-rate", type=float, default=0.08)
    parser.add_argument("--otlp-endpoint", default="http://localhost:4317")
    parser.add_argument("--flush-wait", type=float, default=8.0)
    args = parser.parse_args()

    print(f"Creating tracers for {len(SERVICES)} services...")
    tracers = setup_tracers(args.otlp_endpoint)

    print(f"Generating {args.count} traces (anomaly rate: {args.anomaly_rate*100:.0f}%)...")
    for i in range(args.count):
        generate_trace(tracers, i, args.anomaly_rate)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{args.count} traces sent...")

    print(f"Done. Waiting {args.flush_wait}s for batch exporters to flush...")
    time.sleep(args.flush_wait)

    print("Traces should now be visible: http://localhost:16686")
    print("\nNow run:")
    print("  topology-map render --highlight-anomalies")
    print("  open topology.html")


if __name__ == "__main__":
    main()
