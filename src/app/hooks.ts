/* eslint-disable no-restricted-imports */
import { useDispatch, useSelector } from "react-redux";
import { selectToken, setAuthData } from "../features/Login/LoginSlice";
import { useEffect } from "react";
import { useLazyGetCurrentUserByIdQuery } from "../features/Login/LoginApi";
import { checkTokenLocalStorage } from "../utils/utils";
import { logout } from "../features/Login/LoginSlice";
import type { AppDispatch, RootState } from "./store";
import type { FetchBaseQueryError } from "@reduxjs/toolkit/query/react";

export const useAppDispatch = useDispatch.withTypes<AppDispatch>();
export const useAppSelector = useSelector.withTypes<RootState>();

export const useCheckAuth = () => {
  const [getCurrentUser] = useLazyGetCurrentUserByIdQuery();
  const dispatch = useAppDispatch();
  const token = useSelector(selectToken);
  const effectiveToken = token ?? checkTokenLocalStorage();


  useEffect(() => {
    const check = async () => {
      if (!effectiveToken) {
        dispatch(logout());
        return;
      }

      try {
        const userData = await getCurrentUser(effectiveToken).unwrap();
        dispatch(setAuthData({ user: userData, token: effectiveToken }));
      } catch (err) {
        const error = err as FetchBaseQueryError;
        console.log("Ошибка:", error.data ?? error);
        dispatch(logout());
      }
    };
    check().catch(console.error);
  }, [effectiveToken, dispatch, getCurrentUser]);
};
