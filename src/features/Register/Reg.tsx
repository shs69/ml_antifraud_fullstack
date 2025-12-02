import { motion } from "motion/react";
import { useState, type JSX } from "react";
import { useNavigate } from "react-router-dom";
import { setToken, setUser } from "../Login/LoginSlice";
import { validateReg } from "../../utils/utils";
import { useRegisterMutation } from "./RegApi";
import {
  useLazyGetCurrentUserQuery,
  useLoginMutation,
} from "../Login/LoginApi";
import { useAppDispatch } from "../../app/hooks";
import { type FetchBaseQueryError } from "@reduxjs/toolkit/query/react";
import "./Reg.scss";

export const Reg = (): JSX.Element => {
  const navigate = useNavigate();
  const [register] = useRegisterMutation();
  const [login] = useLoginMutation();
  const [getCurrentUser] = useLazyGetCurrentUserQuery();
  const dispatch = useAppDispatch();
  const [errors, setErrors] = useState({
    email: "",
    password: "",
    fullName: "",
    homeAddress: "",
  });

  const registerFn = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const values = Object.fromEntries(formData.entries()) as {
      email: string;
      password: string;
      fullName: string;
      homeAddress: string;
    };

    if (
      !validateReg(
        values.email,
        values.password,
        values.homeAddress,
        values.fullName,
        setErrors,
      )
    ) {
      setTimeout(() => {
        setErrors({
          email: "",
          password: "",
          fullName: "",
          homeAddress: "",
        });
      }, 400);
      return;
    }

    try {
      await register(values).unwrap();
      const data = await login({
        username: values.email,
        password: values.password,
      }).unwrap();
      dispatch(setToken(data.access_token));
      const user = await getCurrentUser().unwrap();
      dispatch(setUser(user));
      localStorage.setItem("token", data.access_token);
      void navigate("/home");
    } catch (err) {
      const error = err as FetchBaseQueryError;
      console.error(error);
    }

    return event;
  };

  return (
    <div className="reg">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        transition={{ duration: 0.3, ease: "easeInOut" }}
        className="page"
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "100vh",
        }}
      >
        <div className="reg__form form">
          <h1>Создание аккаунта</h1>
          <div className="form__container">
            <form onSubmit={e => void registerFn(e)}>
              <label className="email">
                <div
                  className={
                    errors.email ? "error" : "form__container_label_text"
                  }
                >
                  Электронная почта
                </div>
                <input name="email" type="email" id="email" />
              </label>
              <label className="fullName">
                <div
                  className={
                    errors.fullName ? "error" : "form__container_label_text"
                  }
                >
                  ФИО
                </div>
                <input name="fullName" type="text" id="fullName" />
              </label>
              <label className="address">
                <div
                  className={
                    errors.homeAddress ? "error" : "form__container_label_text"
                  }
                >
                  Домашний адрес
                </div>
                <input name="homeAddress" type="text" id="homeAddress" />
              </label>
              <label className="password">
                <div
                  className={
                    errors.password ? "error" : "form__container_label_text"
                  }
                >
                  Пароль
                </div>
                <input name="password" type="password" id="password" />
              </label>
              <div className="form__container_button_cont">
                <button className="button" type="submit">
                  Создать
                </button>
              </div>
            </form>
          </div>
          <div className="form__container_register">
            <span>Уже есть аккаунт?</span>
            <a onClick={() => void navigate("/login")}>Войти в аккаунт</a>
          </div>
        </div>
      </motion.div>
    </div>
  );
};
