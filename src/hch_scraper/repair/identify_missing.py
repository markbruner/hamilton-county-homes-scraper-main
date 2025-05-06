def find_missing_rows(df, required_columns):
    parcel_numbers = df[df[required_columns].isnull().any(axis=1)]['parcel_number'].to_list()
    transfer_dates = df[df[required_columns].isnull().any(axis=1)]['transfer_date'].to_list()
    return parcel_numbers, transfer_dates