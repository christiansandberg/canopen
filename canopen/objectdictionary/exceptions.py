class OdError(Exception):
    pass


class OdIndexError(OdError):
    """Raised if an index does not exist in the object dictionary"""
    pass


class OdSubIndexError(OdError):
    """Raised if a sub-index does not exist in the object dictionary"""
    pass


class OdNoDataError(OdError):
    """Raised if the data of a object dictionary entry is not set (None)"""
    pass
