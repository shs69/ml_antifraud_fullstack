import type { FetchBaseQueryError } from "@reduxjs/toolkit/query/react";
import { motion } from "motion/react";
import { forwardRef, type JSX, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppDispatch } from "../../app/hooks";
import { useLazyGetCurrentUserQuery, useLoginMutation } from "./LoginApi";
import { setToken, setUser } from "./LoginSlice";
import "./Login.scss";
import { validateLogin } from "../../utils/utils";

export const Login = forwardRef<HTMLDivElement>((_, ref): JSX.Element => {
	const dispatch = useAppDispatch();
	const [login] = useLoginMutation();
	const [getCurrentUser] = useLazyGetCurrentUserQuery();
	const navigate = useNavigate();
	const [errors, setErrors] = useState({
		email: "",
		password: "",
	});

	const logIn = async (e: React.FormEvent<HTMLFormElement>) => {
		e.preventDefault();
		const formData = new FormData(e.currentTarget);
		const values = Object.fromEntries(formData.entries()) as {
			username: string;
			password: string;
		};

		if (!validateLogin(values.username, values.password, setErrors)) {
			setTimeout(() => {
				setErrors({
					email: "",
					password: "",
				});
			}, 400);
			return;
		}

		try {
			const data = await login(values).unwrap();
			dispatch(setToken(data.access_token));
			const user = await getCurrentUser().unwrap();
			dispatch(setUser(user));
			localStorage.setItem("token", data.access_token);
			void navigate("/home");
		} catch (err) {
			const error = err as FetchBaseQueryError;
			console.log("Ошибка:", error.data ?? error);
		}
	};

	return (
		<div className="login" ref={ref}>
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
				<div className="login__form form">
					<h1> Добро пожаловать </h1>
					<div className="form__container">
						<form onSubmit={(e) => void logIn(e)}>
							<label className="email">
								<div
									className={
										errors.email ? "error" : "form__container_label_text"
									}
								>
									Электронная почта
								</div>
								<input name="username" type="email" id="email"></input>
							</label>
							<label className="password">
								<div
									className={
										errors.password ? "error" : "form__container_label_text"
									}
								>
									Пароль
								</div>
								<input name="password" type="password" id="password"></input>
							</label>
							<div className="form__container_button_cont">
								<button className="button" type="submit">
									Войти
								</button>
							</div>
						</form>
					</div>
					<div className="form__container_register">
						<span>Ещё нет аккаунта?</span>
						<a onClick={() => void navigate("/reg")}>Создать аккаунт</a>
					</div>
				</div>
			</motion.div>
		</div>
	);
});
