// SON.Desktop/ViewModels/ViewModelBase.cs — Base Class for ViewModels
using CommunityToolkit.Mvvm.ComponentModel;

namespace SON.Desktop.ViewModels
{
    public abstract class ViewModelBase : ObservableObject
    {
        public virtual void OnNavigatedTo() { }
        public virtual void OnNavigatedFrom() { }
    }
}

