class CodedApplicationError(ValueError):
    code = "validation_failed"


class SelectionNotFoundError(CodedApplicationError):
    code = "selection_not_found"


class OutsideSelectionError(CodedApplicationError):
    code = "outside_selected_area"


class InvalidChangeSetError(CodedApplicationError):
    code = "invalid_change_set"


class BlockNotFoundConflictError(CodedApplicationError):
    code = "selection_not_found"


class BlockChangedConflictError(CodedApplicationError):
    code = "block_changed"
