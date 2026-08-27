    body = (
        f"sm_fusion_requests_total {int(snapshot['requests_total'])}\\n"
        f"sm_fusion_errors_total {int(snapshot['errors_total'])}\\n"
    )