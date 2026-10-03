"""Forward sandbox webhooks; save their signing secret locally without printing it."""

import os
import re
import subprocess
from pathlib import Path

EVENTS = (
    "invoice.paid,invoice.payment_failed,customer.subscription.created,"
    "customer.subscription.updated,customer.subscription.deleted,"
    "checkout.session.completed,charge.refunded,charge.dispute.created"
)


def main():
    key = os.environ.get("AEDROVA_STRIPE_KEY", "")
    if not key.startswith(("sk_test_", "rk_test_")):
        raise SystemExit("Configure a Stripe test key locally first. Live keys are rejected.")
    path = Path(".env.billing")
    if not path.is_file():
        raise SystemExit("The prepared .env.billing file is missing.")
    environment = dict(os.environ, STRIPE_API_KEY=key)
    child = subprocess.Popen(
        [
            "stripe",
            "listen",
            "--events",
            EVENTS,
            "--forward-to",
            "http://127.0.0.1:8092/stripe/webhook",
        ],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    ready = False
    try:
        for line in child.stdout:
            match = re.search(r"whsec_[A-Za-z0-9]+", line)
            if match:
                secret = match.group()
                lines = path.read_text().splitlines()
                replacement = "AEDROVA_WEBHOOK_SECRET=" + secret
                lines = [
                    replacement if item.startswith("AEDROVA_WEBHOOK_SECRET=") else item
                    for item in lines
                ]
                if not any(item.startswith("AEDROVA_WEBHOOK_SECRET=") for item in lines):
                    lines.append(replacement)
                temporary = path.with_suffix(".billing.tmp")
                temporary.write_text("\n".join(lines) + "\n")
                temporary.chmod(0o600)
                temporary.replace(path)
                ready = True
                print(
                    "Sandbox webhook listener ready. "
                    "Signing secret saved privately in .env.billing.",
                    flush=True,
                )
            elif ready and ("-->" in line or "<--" in line):
                print(
                    "Sandbox webhook forwarded; verify acceptance in the application ledger.",
                    flush=True,
                )
        if child.wait() != 0:
            raise SystemExit("Stripe forwarding stopped. Check test access and connectivity.")
    except KeyboardInterrupt:
        child.terminate()
        child.wait(timeout=10)


if __name__ == "__main__":
    main()
