let captureProtected = false;

export function protectCapture(value: boolean) {
  captureProtected = value;
}

export function canLeaveCapture() {
  return (
    !captureProtected ||
    window.confirm(
      "This recording has not been saved. Leave and discard it? Cancel to download it or create a report first.",
    )
  );
}

export function navigate(route: string) {
  window.location.hash = route;
}
