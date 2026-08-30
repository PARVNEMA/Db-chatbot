import { LoginForm } from "@/components/auth/login-form";

export const metadata = {
  title: "Sign In — NL-DB Query Platform",
  description: "Sign in to your account to query your databases in natural language",
};

export default function LoginPage() {
  return <LoginForm />;
}
