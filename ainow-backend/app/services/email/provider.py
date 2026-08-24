from abc import ABC, abstractmethod


class EmailProvider(ABC):

    @abstractmethod
    def send(
        self,
        recipient_email: str,
        subject: str,
        html_content: str,
        idempotency_key: str,
    ) -> str:
        """
        Send an email.

        Returns:
            Provider message ID.
        """
        raise NotImplementedError