import {
  Button,
  FieldError,
  Form,
  type FormProps,
  Input,
  Label,
  TextField,
} from "react-aria-components";
import { Navigate, useLocation } from "react-router";

import { t } from "../../lib/i18n";
import { useCurrentUser } from "./currentUser";
import { loginErrorMessage, useLogin } from "./login";
import styles from "./LoginPage.module.css";
import { returnAddress } from "./RequireAuth";

function formValue(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value : "";
}

export function LoginPage() {
  const login = useLogin();
  const { data: user } = useCurrentUser();
  const location = useLocation();

  // Typed by React Aria's Form itself: React's types and React Aria's currently disagree on
  // the name of the submit event type.
  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const credentials = {
      username: formValue(form, "username"),
      password: formValue(form, "password"),
    };
    login.mutate(credentials);
  };

  // Once someone is logged in, whether just now or before opening this page, go on to where
  // they wanted to be. A successful login stores the user, which brings us here again.
  if (user) {
    return <Navigate to={returnAddress(location.state)} replace />;
  }

  return (
    <div className={styles.page}>
      <h1>{t("login.title")}</h1>
      <Form className={styles.form} onSubmit={handleSubmit}>
        <TextField className={styles.field} name="username" autoComplete="username" isRequired>
          <Label>{t("login.username")}</Label>
          <Input className={styles.input} />
          <FieldError className={styles.error} />
        </TextField>
        <TextField
          className={styles.field}
          name="password"
          type="password"
          autoComplete="current-password"
          isRequired
        >
          <Label>{t("login.password")}</Label>
          <Input className={styles.input} />
          <FieldError className={styles.error} />
        </TextField>
        {login.isError && (
          // role="alert": screen readers announce the message as soon as it appears.
          <p className={styles.error} role="alert">
            {loginErrorMessage(login.error)}
          </p>
        )}
        <Button className={styles.button} type="submit" isPending={login.isPending}>
          {t("login.submit")}
        </Button>
      </Form>
    </div>
  );
}
