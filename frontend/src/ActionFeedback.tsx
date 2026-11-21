export type Feedback = {
  kind: "pending" | "success" | "error";
  message: string;
};

export type Action = (
  task: () => Promise<unknown>,
  message?: string,
  report?: (feedback: Feedback) => void,
) => Promise<void>;

export function ActionFeedback({ feedback }: { feedback: Feedback | null }) {
  if (!feedback) return null;
  return (
    <p
      className={`action-feedback ${feedback.kind}`}
      role={feedback.kind === "error" ? "alert" : "status"}
    >
      {feedback.message}
    </p>
  );
}
