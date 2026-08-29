from pydantic import BaseModel


class Money(BaseModel):
    """Money is always transmitted as integer paise (never a float) plus a
    formatted display string computed server-side, so the frontend never
    does its own paise/rupee arithmetic."""
    paise: int
    display: str  # e.g. "₹18,42,580.00" (Indian digit grouping)

    @staticmethod
    def of(paise: int) -> "Money":
        return Money(paise=paise, display=format_inr(paise))


def format_inr(paise: int) -> str:
    """Indian digit grouping: last 3 digits, then groups of 2. E.g. 1242580 -> '12,42,580'."""
    rupees = paise / 100
    sign = "-" if rupees < 0 else ""
    whole = int(abs(rupees))
    frac = abs(rupees) - whole
    s = str(whole)
    if len(s) <= 3:
        grouped = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last3
    return f"₹{sign}{grouped}.{round(frac*100):02d}"


class ErrorResponse(BaseModel):
    detail: str
    error_type: str | None = None
