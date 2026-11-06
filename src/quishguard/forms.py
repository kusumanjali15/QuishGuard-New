"""Helpers for reading HTML form data."""

from urllib.parse import parse_qs


def parse_form_body(raw_body: str) -> dict[str, str]:
    """Turn a URL-encoded form body into a dict of field name -> value.

    Example: "username=demo_user_01&password=Lab-Pass-4821"
          -> {"username": "demo_user_01", "password": "Lab-Pass-4821"}
    """
    fields = parse_qs(raw_body, keep_blank_values=True)
    return {name: values[0] for name, values in fields.items()}
    
