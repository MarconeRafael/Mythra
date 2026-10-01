"""Exceções compartilhadas entre casos de uso e transporte HTTP."""


class ResourceNotFoundError(Exception):
    """Indica que um recurso solicitado não existe no escopo informado."""


class ConflictError(Exception):
    """Indica conflito com uma regra de unicidade ou integridade do domínio."""
