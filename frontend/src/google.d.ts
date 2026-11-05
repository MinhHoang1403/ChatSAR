interface GoogleIdentityApi {
  initialize(config: {
    client_id: string;
    nonce: string;
    callback: (response: { credential: string }) => void;
  }): void;
  renderButton(element: HTMLElement, options: { theme: string; size: string; text: string }): void;
  disableAutoSelect(): void;
}

interface Window {
  google?: { accounts: { id: GoogleIdentityApi } };
}
