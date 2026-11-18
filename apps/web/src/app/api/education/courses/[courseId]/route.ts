import { coursePath, relayAuthenticated } from "@/lib/authenticated-proxy";

export async function GET(request: Request, context: { params: Promise<{ courseId: string }> }) {
  const { courseId } = await context.params;
  const path = coursePath(courseId);
  if (!path) return Response.json({ detail: "Invalid course ID." }, { status: 400 });
  return relayAuthenticated(request, path + "");
}
