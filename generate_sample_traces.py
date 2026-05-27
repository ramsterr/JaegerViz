"""Generate 300 realistic microservice traces in Jaeger API format."""

import json
import random
import sys


def random_hex(length: int) -> str:
    return "".join(random.choice("0123456789abcdef") for _ in range(length))


def random_latency(base: int, variance: float = 0.3) -> int:
    std = base * variance
    return max(100, int(random.gauss(base, std)))


def generate_traces(num_traces: int = 300) -> None:
    random.seed(42)

    # --- service -> processID mapping ---
    proc_ids = {
        "frontend": "pfrontend",
        "cartservice": "pcartservice",
        "redis-cart": "prediscart",
        "productcatalogservice": "pproductcatalogservice",
        "adservice": "padservice",
        "recommendationservice": "precommendationservice",
        "checkoutservice": "pcheckoutservice",
        "shippingservice": "pshippingservice",
        "emailservice": "pemailservice",
        "paymentservice": "ppaymentservice",
        "currencyservice": "pcurrencyservice",
    }

    # --- average latencies in microseconds ---
    latencies = {
        "frontend->cartservice": 45_000,
        "frontend->productcatalogservice": 30_000,
        "frontend->checkoutservice": 60_000,
        "frontend->recommendationservice": 25_000,
        "cartservice->redis-cart": 5_000,
        "checkoutservice->shippingservice": 80_000,
        "checkoutservice->paymentservice": 120_000,
        "checkoutservice->emailservice": 200_000,
        "checkoutservice->currencyservice": 50_000,
        "shippingservice->emailservice": 120_000_000,  # async, ~2 min
        "productcatalogservice->adservice": 20_000,
    }

    # --- path probabilities ---
    prob_cart = 0.80          # frontend -> cartservice
    prob_redis_given_cart = 0.70  # cartservice -> redis-cart (70% of cart traces)
    prob_product = 0.60       # frontend -> productcatalogservice -> adservice
    prob_recommendation = 0.40  # frontend -> recommendationservice
    prob_checkout = 0.30      # frontend -> checkoutservice -> shippingservice -> emailservice

    prob_cart_anomaly = 0.15  # fraction of cartservice spans made 5-15x slower

    cart_anomaly_count = 0
    traces = []

    for i in range(num_traces):
        trace_id = random_hex(32)
        spans = []
        used_services: set[str] = set()

        base_time = 1700000000000000 + i * random.randint(100_000, 5_000_000)

        def add_span(span_id, parent_id, operation, start, duration, service, tags=None):
            spans.append({
                "traceID": trace_id,
                "spanID": span_id,
                "parentSpanID": parent_id,
                "operationName": operation,
                "startTime": start,
                "duration": duration,
                "processID": proc_ids[service],
                "tags": tags or [],
                "flags": 1,
            })
            used_services.add(service)

        # --- root span: frontend ---
        frontend_id = random_hex(16)
        frontend_ops = {
            "cart": "GET /cart",
            "product": "GET /product",
            "checkout": "POST /checkout",
            "recommendation": "GET /recommendations",
            "default": "GET /",
        }

        # which paths are taken for this trace?
        take_cart = random.random() < prob_cart
        take_product = random.random() < prob_product
        take_recommendation = random.random() < prob_recommendation
        take_checkout = random.random() < prob_checkout

        longest_child_end = 0  # track so frontend duration wraps everything

        # --- Path A: cartservice ---
        if take_cart:
            cart_id = random_hex(16)
            cart_latency = random_latency(latencies["frontend->cartservice"])

            is_anomaly = False
            if random.random() < prob_cart_anomaly:
                cart_latency = int(cart_latency * random.uniform(5, 15))
                is_anomaly = True
                cart_anomaly_count += 1

            cart_start = base_time + random.randint(1000, 50_000)
            tags = [{"key": "http.method", "type": "string", "value": "POST"},
                    {"key": "http.url", "type": "string", "value": "/cartservice.AddItem"}]
            if is_anomaly:
                tags.append({"key": "anomaly", "type": "bool", "value": True})
                tags.append({"key": "anomaly.type", "type": "string", "value": "high_latency"})
            add_span(cart_id, frontend_id, "cartservice/AddItem",
                     cart_start, cart_latency, "cartservice", tags)

            end = cart_start + cart_latency
            if end - base_time > longest_child_end:
                longest_child_end = end - base_time

            # redis-cart (70% of cart traces go deeper)
            if random.random() < prob_redis_given_cart:
                redis_id = random_hex(16)
                redis_latency = random_latency(latencies["cartservice->redis-cart"])
                redis_start = cart_start + random.randint(500, max(500, cart_latency // 3))
                add_span(redis_id, cart_id, "redis-cart/HGET",
                         redis_start, redis_latency, "redis-cart",
                         [{"key": "db.type", "type": "string", "value": "redis"}])

                end_r = redis_start + redis_latency
                if end_r - base_time > longest_child_end:
                    longest_child_end = end_r - base_time

        # --- Path B: productcatalogservice -> adservice ---
        if take_product:
            prod_id = random_hex(16)
            prod_latency = random_latency(latencies["frontend->productcatalogservice"])
            prod_start = base_time + random.randint(1000, 50_000)
            add_span(prod_id, frontend_id, "productcatalogservice/GetProduct",
                     prod_start, prod_latency, "productcatalogservice",
                     [{"key": "http.method", "type": "string", "value": "GET"}])

            end = prod_start + prod_latency
            if end - base_time > longest_child_end:
                longest_child_end = end - base_time

            # adservice
            ad_id = random_hex(16)
            ad_latency = random_latency(latencies["productcatalogservice->adservice"])
            ad_start = prod_start + random.randint(500, max(500, prod_latency // 3))
            add_span(ad_id, prod_id, "adservice/GetAds",
                     ad_start, ad_latency, "adservice",
                     [{"key": "http.method", "type": "string", "value": "GET"},
                      {"key": "http.url", "type": "string", "value": "/adservice.GetAds"}])

            end_a = ad_start + ad_latency
            if end_a - base_time > longest_child_end:
                longest_child_end = end_a - base_time

        # --- Path C: recommendationservice ---
        if take_recommendation:
            rec_id = random_hex(16)
            rec_latency = random_latency(latencies["frontend->recommendationservice"])
            rec_start = base_time + random.randint(1000, 50_000)
            add_span(rec_id, frontend_id, "recommendationservice/ListRecommendations",
                     rec_start, rec_latency, "recommendationservice",
                     [{"key": "http.method", "type": "string", "value": "GET"}])

            end = rec_start + rec_latency
            if end - base_time > longest_child_end:
                longest_child_end = end - base_time

        # --- Path D: checkoutservice -> shippingservice -> emailservice ---
        if take_checkout:
            checkout_id = random_hex(16)
            checkout_latency = random_latency(latencies["frontend->checkoutservice"])
            checkout_start = base_time + random.randint(1000, 50_000)
            add_span(checkout_id, frontend_id, "checkoutservice/PlaceOrder",
                     checkout_start, checkout_latency, "checkoutservice",
                     [{"key": "http.method", "type": "string", "value": "POST"}])

            end = checkout_start + checkout_latency
            if end - base_time > longest_child_end:
                longest_child_end = end - base_time

            # shippingservice
            ship_id = random_hex(16)
            ship_latency = random_latency(latencies["checkoutservice->shippingservice"])
            ship_start = checkout_start + random.randint(1000, 20_000)
            add_span(ship_id, checkout_id, "shippingservice/ShipOrder",
                     ship_start, ship_latency, "shippingservice",
                     [{"key": "http.method", "type": "string", "value": "POST"}])

            # shippingservice -> emailservice (async, ~2 min)
            email_id = random_hex(16)
            email_latency = random_latency(latencies["shippingservice->emailservice"], variance=0.1)
            email_start = ship_start + random.randint(1000, 30_000)
            add_span(email_id, ship_id, "emailservice/SendShipmentConfirmation",
                     email_start, email_latency, "emailservice",
                     [{"key": "async", "type": "bool", "value": True},
                      {"key": "http.method", "type": "string", "value": "POST"}])

            end_e = email_start + email_latency
            if end_e - base_time > longest_child_end:
                longest_child_end = end_e - base_time

            # paymentservice (70% probability within a checkout)
            if random.random() < 0.70:
                pay_id = random_hex(16)
                pay_latency = random_latency(latencies["checkoutservice->paymentservice"])
                pay_start = checkout_start + random.randint(1000, 15_000)
                add_span(pay_id, checkout_id, "paymentservice/Charge",
                         pay_start, pay_latency, "paymentservice",
                         [{"key": "http.method", "type": "string", "value": "POST"}])

                end_p = pay_start + pay_latency
                if end_p - base_time > longest_child_end:
                    longest_child_end = end_p - base_time

            # emailservice (direct from checkout, 50% probability)
            if random.random() < 0.50:
                email2_id = random_hex(16)
                email2_latency = random_latency(latencies["checkoutservice->emailservice"])
                email2_start = checkout_start + random.randint(10_000, 30_000)
                add_span(email2_id, checkout_id, "emailservice/SendOrderConfirmation",
                         email2_start, email2_latency, "emailservice",
                         [{"key": "http.method", "type": "string", "value": "POST"}])

                end_e2 = email2_start + email2_latency
                if end_e2 - base_time > longest_child_end:
                    longest_child_end = end_e2 - base_time

            # currencyservice (30% probability within a checkout)
            if random.random() < 0.30:
                curr_id = random_hex(16)
                curr_latency = random_latency(latencies["checkoutservice->currencyservice"])
                curr_start = checkout_start + random.randint(500, 10_000)
                add_span(curr_id, checkout_id, "currencyservice/Convert",
                         curr_start, curr_latency, "currencyservice",
                         [{"key": "http.method", "type": "string", "value": "POST"}])

                end_c = curr_start + curr_latency
                if end_c - base_time > longest_child_end:
                    longest_child_end = end_c - base_time

        # --- pick a frontend operation name ---
        if take_checkout:
            frontend_op = frontend_ops["checkout"]
        elif take_cart:
            frontend_op = frontend_ops["cart"]
        elif take_product:
            frontend_op = frontend_ops["product"]
        elif take_recommendation:
            frontend_op = frontend_ops["recommendation"]
        else:
            frontend_op = frontend_ops["default"]

        frontend_duration = max(100_000, longest_child_end + random.randint(1000, 10_000))
        add_span(frontend_id, "", frontend_op,
                 base_time, frontend_duration, "frontend",
                 [{"key": "http.method", "type": "string", "value": "GET"},
                  {"key": "http.status_code", "type": "int64", "value": 200 if random.random() > 0.05 else 500}])

        # --- build processes map for this trace ---
        processes = {}
        for svc in used_services:
            processes[proc_ids[svc]] = {"serviceName": svc, "tags": []}

        traces.append({
            "traceID": trace_id,
            "spans": spans,
            "processes": processes,
        })

    # --- write output ---
    result = {
        "data": traces,
        "total": num_traces,
        "limit": num_traces,
        "offset": 0,
    }

    with open("sample_traces.json", "w") as f:
        json.dump(result, f, indent=2)

    # --- summary ---
    all_services: set[str] = set()
    for t in traces:
        for pid, pinfo in t["processes"].items():
            all_services.add(pinfo["serviceName"])

    print(f"Generated {num_traces} traces")
    print(f"Services found: {len(all_services)} — {sorted(all_services)}")
    print(f"Cartservice anomaly injections: {cart_anomaly_count} spans "
          f"({100 * cart_anomaly_count / num_traces:.1f}% of traces)")


if __name__ == "__main__":
    generate_traces()
