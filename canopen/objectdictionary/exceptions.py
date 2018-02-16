class OdError(Exception):
    pass


class OdIndexError(OdError):
    """Raised if an index does not exist in the object dictionary"""
    pass


class OdSubIndexError(OdError):
    """Raised if a sub-index does not exist in the object dictionary"""
    pass
