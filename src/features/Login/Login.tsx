import type { JSX } from "react";
import { useAppDispatch } from "../../app/hooks";
import { setToken, setUser } from "./LoginSlice";
import { useLazyGetCurrentUserQuery, useLoginMutation } from "./LoginApi";
import type { FetchBaseQueryError } from "@reduxjs/toolkit/query/react";
import "./Login.scss";

export const Login = (): JSX.Element => {
  const dispatch = useAppDispatch();
  const [login] = useLoginMutation();
  const [getCurrentUser] = useLazyGetCurrentUserQuery();

  const logIn = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const values = Object.fromEntries(formData.entries()) as {
      username: string;
      password: string;
    };

    try {
      const data = await login(values).unwrap();
      dispatch(setToken(data.access_token));
      const user = await getCurrentUser().unwrap();
      dispatch(setUser(user));
      localStorage.setItem("token", data.access_token);
      console.log("Пользователь:", user);
    } catch (err) {
      const error = err as FetchBaseQueryError;
      console.log("Ошибка:", error.data ?? error);
    }
  };

  return (
    <div className="login">
      <div className="login__form">
        <h1> Добро пожаловать </h1>
        <div className="login__container">
          <form onSubmit={e => void logIn(e)}>
            <label>
              Электронная почта
              <input name="username" type="email" id="email"></input>
            </label>
            <label>
              Пароль
              <input name="password" type="password" id="password"></input>
            </label>
            <div className="login__container_button_cont">
              <button className="button" type="submit">
                Войти
              </button>
            </div>
          </form>
        </div>
        <p>
          Ещё не зарегистрированы?
          <a>Зарегистрироваться</a>
        </p>
      </div>
    </div>
  );
};
