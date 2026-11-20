export async function api<T = unknown>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const multipart = data instanceof FormData;
  const result = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: {
      "X-AA-Request": "1",
      ...(!multipart && data !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
    },
    body:
      data === undefined ? undefined : multipart ? data : JSON.stringify(data),
  });
  if (!result.ok) {
    let error;
    try {
      error = await result.json();
    } catch {
      error = { detail: "Não foi possível concluir a operação." };
    }
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "Confira os campos preenchidos.",
    );
  }
  return result.json();
}
